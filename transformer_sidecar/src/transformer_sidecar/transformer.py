# Copyright (c) 2022, University of Illinois/NCSA
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import json
import os
import shutil
import timeit
from argparse import Namespace
from hashlib import sha1, sha256
from multiprocessing import Queue
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple, Optional, Union

import kombu
import psutil as psutil
import time
from celery import Celery, shared_task

from transformer_sidecar.science_container_command import ScienceContainerCommand
from transformer_sidecar.transformer_logging import initialize_logging
from transformer_sidecar.transformer_stats import TransformerStats
from transformer_sidecar.transformer_stats.aod_stats import AODStats  # NOQA: 401
from transformer_sidecar.transformer_stats.uproot_stats import UprootStats  # NOQA: 401
from transformer_sidecar.transformer_stats.raw_uproot_stats import RawUprootStats  # NOQA: 401
from transformer_sidecar.object_store_manager import ObjectStoreManager
from transformer_sidecar.object_store_uploader import ObjectStoreUploader, WorkQueueItem
from transformer_sidecar.servicex_adapter import ServiceXAdapter, FileCompleteRecord
from transformer_sidecar.transformer_argument_parser import TransformerArgumentParser

# Module globals
shared_dir: Optional[str] = None
object_store = None
posix_path: str = ""
startup_time = None
convert_root_to_parquet: bool = False

upload_queue: Optional[Queue] = None
uploader: Optional[ObjectStoreUploader] = None

science_container: Optional[ScienceContainerCommand] = None
transformer_capabilities: dict = {}
celery_app: Optional[Celery] = None

request_id: str = ""

# Use this to make sure we don't generate output file names that are crazy long
MAX_PATH_LEN = 255

PLACE = {
    "host_name": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown"),
}


start_time = timeit.default_timer()
logger = initialize_logging()


@shared_task
def transform_file(
        request_id,
        file_id,
        paths: list[str],
        service_endpoint,
        result_destination,
        result_format):
    """
    This is the main function for the transformer. It is called whenever a new message
    is available on the rabbit queue. These messages represent a single file to be
    transformed.

    Each request may include a list of replicas to try. This service will loop through
    the replicas and produce a json document for the science package to actually work from.
    This control document will have the replica for it to try to transform along with a
    path in the output directory for the generated parquet or root file to be written.

    This control document is sent via a socket to the science image.
    Once science image has done its job, it sends back a message over the socket.
    The sidecar will then add the parquet/root file in the output directory to the
    S3 upload queue.

    We will examine this log file to see if the transform succeeded or failed
    """

    global shared_dir

    transform_request = {
        "file-id": file_id,
        "request-id": request_id,
        "status": "unknown",
        "error": None,
    }

    # If we are converting root to parquet here, then the transformer
    # doesn't need to know about. Tell it to write root, and we'll take it from here
    if convert_root_to_parquet:
        result_format = "root"

    # Prioritize the replicas
    _file_paths = prioritize_replicas(paths)

    # adding cache prefix
    _file_paths = prepend_xcache(_file_paths)

    logger.info(
        "got transform request.",
        extra={
            "requestId": request_id,
            "paths": _file_paths,
            "result-destination": result_destination,
            "result-format": result_format,
            "service-endpoint": service_endpoint,
            "place": PLACE,
        },
    )
    servicex = ServiceXAdapter(service_endpoint)

    # creating output dir for transform output files
    request_path = os.path.join(shared_dir, request_id)
    os.makedirs(request_path, exist_ok=True)

    # scratch dir where the transformer temporarily writes the results.
    scratch_path = os.path.join(request_path, "scratch")
    os.makedirs(scratch_path, exist_ok=True)

    start_process_info = get_process_info()
    total_time = time.time()

    transform_success = False
    transformer_stats = TransformerStats()
    try:
        # Loop through the replicas
        for _file_path in _file_paths:
            logger.info(
                "trying to transform file",
                extra={
                    "requestId": request_id,
                    "file-path": _file_path,
                    "place": PLACE,
                },
            )

            transform_request["file-path"] = _file_path

            # Enrich the transform request to give more hints to the science container
            transform_request["downloadPath"] = _file_path

            # Decide an optional file extension for the results. If the output format is
            # parquet then we add that as an extension, otherwise stick with the format
            # of the input file.
            result_extension = ".parquet" if result_format == "parquet" else ""
            hashed_file_name = hash_path(
                _file_path.replace("/", ":") + result_extension
            )

            # The transformer will write results here as they are generated. This
            # directory isn't monitored.
            if result_destination == "volume":
                transform_request["safeOutputFileName"] = \
                    os.path.join(posix_path, hashed_file_name)
            else:
                transform_request["safeOutputFileName"] = \
                    os.path.join(scratch_path, hashed_file_name)

            transform_request['result-format'] = result_format
            science_container.synch()
            science_container.send(transform_request)
            science_container_response = science_container.await_response()

            transform_request["status"] = science_container_response

            # Grab the logs
            transformer_stats = fill_stats_parser(
                transformer_capabilities["stats-parser"],
                Path(os.path.join(request_path, "abc.log")),
            )
            if science_container_response == "success.":
                rec = FileCompleteRecord(
                    request_id=request_id,
                    file_path=_file_path,
                    file_id=file_id,
                    status="success",
                    total_time=time.time() - total_time,
                    total_events=transformer_stats.total_events,
                    total_bytes=transformer_stats.file_size,
                )

                if object_store:
                    upload_queue.put(
                        WorkQueueItem(
                            Path(transform_request["safeOutputFileName"]), servicex, rec
                        )
                    )
                else:
                    servicex.put_file_complete(rec)

                transform_success = True
                ts = {
                    "requestId": request_id,
                    "file-size": transformer_stats.file_size,
                    "total-events": transformer_stats.total_events,
                    "place": PLACE,
                }
                logger.info("Transformer stats.", extra=ts)
                science_container.confirm()
                break

            science_container.confirm()

        # If none of the replicas resulted in a successful transform then we have
        # a hard failure with this file.
        if not transform_success:
            hf = {
                "requestId": request_id,
                "file-path": _file_paths[0],
                "file-id": file_id,
                "place": PLACE,
                "transform-log": transformer_stats.log_body,
            }
            logger.error(f"Hard Failure: {transformer_stats.error_info}", extra=hf)

        if not transform_success:
            rec = FileCompleteRecord(
                request_id=request_id,
                file_path=_file_paths[0],
                file_id=file_id,
                status="failure",
                total_time=time.time() - total_time,
                total_events=0,
                total_bytes=0,
            )
            servicex.put_file_complete(rec)

        stop_process_info = get_process_info()
        elapsed_times = TimeTuple(
            user=stop_process_info.user - start_process_info.user,
            system=stop_process_info.system - start_process_info.system,
            iowait=stop_process_info.iowait - start_process_info.iowait,
        )

        logger.info(
            "File processed.",
            extra={
                "requestId": request_id,
                "fileId": file_id,
                "user": elapsed_times.user,
                "sys": elapsed_times.system,
                "iowait": elapsed_times.iowait,
                "place": PLACE,
            },
        )

    except Exception as error:
        logger.exception(f"Received exception doing transform: {error}")
        rec = FileCompleteRecord(
            request_id=request_id,
            file_path=_file_paths[0],
            file_id=file_id,
            status="failure",
            total_time=time.time() - total_time,
            total_events=0,
            total_bytes=0,
        )
        servicex.put_file_complete(rec)


class TimeTuple(NamedTuple):
    """
    Named tuple to store process time information.
    Immutable so values can't be accidentally altered after creation
    """

    user: float
    system: float
    iowait: float

    @property
    def total_time(self):
        """
        Return total time spent by process

        :return: sum of user, system, iowait times
        """
        return self.user + self.system + self.iowait


def read_capabilities_file() -> dict[str, str]:
    """
    The capabilities file is mounted in the pod at startup. It's possible for
    the code to start before the file is available. We'll wait for it here.
    """
    global shared_dir
    logger.debug("Waiting for capabilities file")
    capabilities_file_path = Path(
        os.path.join(shared_dir, "transformer_capabilities.json")
    )
    while not capabilities_file_path.is_file():
        time.sleep(1)

    with open(capabilities_file_path) as capabilities_file:
        return json.load(capabilities_file)


def init(args: Union[Namespace, SimpleNamespace], app: Celery) -> None:
    global convert_root_to_parquet, startup_time, upload_queue, \
        object_store, posix_path, science_container, uploader, \
        shared_dir, transformer_capabilities, request_id, celery_app

    shared_dir = args.shared_dir
    request_id = args.request_id
    celery_app = app

    if args.result_destination == "object-store":
        posix_path = args.shared_dir
        object_store = ObjectStoreManager()
    elif args.output_dir:
        object_store = None
        posix_path = args.output_dir

    os.makedirs(shared_dir, exist_ok=True)

    # create scripts dir for access by science container
    scripts_path = os.path.join(shared_dir, "scripts")
    os.makedirs(scripts_path, exist_ok=True)
    shutil.copy("scripts/watch.sh", scripts_path)
    shutil.copy("scripts/proxy-exporter.sh", scripts_path)

    transformer_capabilities = read_capabilities_file()

    # If the user requested Parquet, but the transformer isn't capable of producing it,
    # then we will need to convert here in the sidecar....
    convert_root_to_parquet = (
        args.result_format == "parquet"
        and "parquet" not in transformer_capabilities["file-formats"]
    )

    startup_time = get_process_info()
    logger.info(
        "Startup finished.",
        extra={
            "user": startup_time.user,
            "sys": startup_time.system,
            "iowait": startup_time.iowait,
            "place": PLACE,
        },
    )

    science_container = ScienceContainerCommand()
    logger.debug("Connected to science container", extra={"place": PLACE})

    if object_store:
        # Create a queue to communicate with the ObjectStore uploader
        upload_queue = Queue()

        uploader = ObjectStoreUploader(
            request_id=args.request_id,
            input_queue=upload_queue,
            logger=logger,
            convert_root_to_parquet=convert_root_to_parquet,
        )

        uploader.start()

    app.worker_main(
        argv=[
            "worker",
            "--concurrency=1",  # Don't allow multiple files to be processed at once
            "--without-mingle",
            "--without-gossip",
            "--without-heartbeat",
            "--loglevel=info",
            "-Q", f"transformer-{args.request_id}",
            "-n",
            f"transformer-{args.request_id}@%h",
        ]
    )


def prioritize_replicas(replicas: list[str]) -> list[str]:
    """
    Prioritizes a list of replicas by placing root replicas (those not starting
    with "http") before HTTP replicas.

    Args:
        replicas (list[str]): A list of replica URLs or paths.

    Returns:
        list[str]: The prioritized list of replicas, with root replicas first and
                    HTTP replicas second.
    """
    http_replicas = [replica for replica in replicas if replica.startswith("http")]
    root_replicas = [replica for replica in replicas if not replica.startswith("http")]
    return root_replicas + http_replicas


def get_process_info():
    """
    Get process information (just cpu, sys, iowait times right now) and
    return it

    :return: TimeTuple with timing information
    """
    process_info = psutil.Process()
    time_stats = process_info.cpu_times()
    iowait = time_stats.iowait if hasattr(time_stats, "iowait") else -1
    return TimeTuple(
        user=time_stats.user + time_stats.children_user,
        system=time_stats.system + time_stats.children_system,
        iowait=iowait,
    )


def hash_path(file_name: str) -> str:
    """
    Make the path safe for object store or POSIX, by keeping the length
    less than MAX_PATH_LEN. Replace the leading (less interesting) characters with a
    forty character hash.
    :param file_name: Input filename
    :return: Safe path string
    """
    if len(file_name) > MAX_PATH_LEN:
        hashed_value = sha1(file_name.encode("utf-8")).hexdigest()
        return "".join(
            [
                "_",
                hashed_value,
                file_name[-1 * (MAX_PATH_LEN - len(hashed_value) - 1):],
            ]
        )
    else:
        return file_name


def fill_stats_parser(stats_parser_name: str, logfile_path: Path) -> TransformerStats:
    # Assume that the stats parser class has been imported
    return globals()[stats_parser_name](logfile_path)


def prepend_xcache(file_paths: list[str]) -> list[str]:
    """
    If a CACHE_PREFIX is given, prepend the file paths with the xcache. If there
    are multiple xcaches, the same file will always be prepended with the same
    xcache. We do this by hashing the file path and then calculating modulo of the
    value.
    """
    prefix = os.environ.get("CACHE_PREFIX", "")

    if not prefix:
        return file_paths

    prefix_list = [p.strip() for p in prefix.split(",")]

    prefixed_paths = []
    for f in file_paths:
        # for each path we get unique hash value
        hex_digest = sha256(f.encode()).hexdigest()

        # we turn file hex_digest into an integer then calculate modulo of the
        # value.
        pinned_xcache_index = int(hex_digest, 16) % len(prefix_list)

        # Construct the path
        prefixed_paths.append(f"root://{prefix_list[pinned_xcache_index]}//{f}")
    return prefixed_paths


if __name__ == "__main__":  # pragma: no cover
    start_time = timeit.default_timer()

    parser = TransformerArgumentParser(description="ServiceX Transformer")
    _args = parser.parse_args()
    app = Celery("transformer_sidecar", broker=_args.rabbit_uri)
    app.conf.task_queues = [
        kombu.Queue(name=f"transformer-{_args.request_id}",
                    durable=False, auto_delete=True)
    ]
    app.conf.task_create_missing_queues = False
    app.conf.worker_hijack_root_logger = False
    app.conf.worker_redirect_stdouts_level = 'DEBUG'
    init(_args, app)

    logger.debug(
        "Shutting down transformer",
        extra={"requestId": request_id, "place": PLACE},
    )
    science_container.close()

    upload_queue.put(WorkQueueItem(None, None))
    uploader.join()  # Wait for the uploader to finish completely
    exit(0)
