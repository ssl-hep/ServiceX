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
import os
import shutil
import sys
import time
import timeit
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Union

import kombu
from celery import Celery, shared_task
from celery.signals import after_setup_logger

from transformer_sidecar.object_store_manager import (
    ObjectStoreError,
    ObjectStoreManager,
)
from transformer_sidecar.science_container_command import (
    ScienceContainerCommand,
    ScienceContainerException,
)
from transformer_sidecar.servicex_adapter import FileCompleteRecord, ServiceXAdapter
from transformer_sidecar.transformer_argument_parser import TransformerArgumentParser
from transformer_sidecar.transformer_logging import initialize_logging, set_request_id
from transformer_sidecar.transformer_stats import TransformerStats

# The helpers are shared with the Temporal pilot (pilot.py). They are imported by
# name so this module's callers and the tests' patches still find them here.
from transformer_sidecar.transform_helpers import (  # noqa: F401
    MAX_PATH_LEN,
    TimeTuple,
    change_davs_to_https,
    convert_to_parquet,
    convert_to_rntuple,
    fill_stats_parser,
    get_process_info,
    hash_path,
    prepend_xcache,
    prioritize_replicas,
)
from transformer_sidecar.transform_helpers import (
    read_capabilities_file as _read_capabilities_file,
)

# Module globals
shared_dir: Optional[str] = None
object_store = None
posix_path: str = ""
startup_time = None
convert_root_to_parquet: bool = False
convert_root_to_rntuple: bool = False

science_container: Optional[ScienceContainerCommand] = None
transformer_capabilities: dict = {}
celery_app: Optional[Celery] = None

request_id: str = ""

PLACE = {
    "host": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown"),
    "pod": os.getenv("POD_NAME", "unknown"),
}


start_time = timeit.default_timer()
logger = initialize_logging()


@shared_task(
    acks_late=True,
)
def transform_file(
    request_id,
    file_id,
    paths: list[str],
    service_endpoint,
    result_destination,
    result_format,
):
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
    The sidecar will then upload the file to object store

    We will examine this log file to see if the transform succeeded or failed
    """

    log_extra = {"request_id": request_id, "file_id": file_id, "place": PLACE}

    transform_request = {
        "file-id": file_id,
        "request-id": request_id,
        "status": "unknown",
    }

    # If we are converting root to another format here, then the transformer
    # doesn't need to know about. Tell it to write root-file, and we'll take it from here
    # At the moment root-file is the one thing we are sure everyone can write
    if convert_root_to_parquet or convert_root_to_rntuple:
        result_format = "root-file"

    # Change davs to https
    _file_paths = change_davs_to_https(paths)

    # Prioritize the replicas
    _file_paths = prioritize_replicas(_file_paths)

    # adding cache prefix
    _file_paths = prepend_xcache(_file_paths)

    logger.info(
        "got transform request.",
        extra={**log_extra, "replicas": _file_paths, "result_path": result_destination},
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
                    **log_extra,
                    "input_path": _file_path,
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
                _file_path.replace("/", "_").replace(":", "_") + result_extension
            )

            # The transformer will write results here as they are generated. This
            # directory isn't monitored.
            if result_destination == "volume":
                transform_request["safeOutputFileName"] = os.path.join(
                    posix_path, hashed_file_name
                )
            else:
                transform_request["safeOutputFileName"] = os.path.join(
                    scratch_path, hashed_file_name
                )

            transform_request["result-format"] = result_format
            science_container.synch()
            science_container.send(transform_request)
            science_container_response = science_container.await_response()

            transform_request["status"] = science_container_response
            logger.info(
                "Science container completed with status %s"
                % science_container_response,
                extra=log_extra,
            )

            # Grab the logs
            transformer_stats = fill_stats_parser(
                transformer_capabilities["stats-parser"],
                Path(os.path.join(request_path, "abc.log")),
            )
            if science_container_response == "success.":
                output_path = Path(transform_request["safeOutputFileName"])
                if not output_path.exists():
                    file_to_upload = None
                else:
                    # Now is the time to convert the file to parquet if that's what the user
                    # requested, but our particular transformer doesn't support it.
                    # Delete source if we did a conversion so it doesn't clutter the POSIX
                    # output if we use that.
                    if convert_root_to_parquet:
                        object_name = output_path.with_suffix(".parquet").name
                        if (
                            file_to_upload := convert_to_parquet(output_path)
                        ) is not None:
                            output_path.unlink()
                    elif convert_root_to_rntuple:
                        object_name = output_path.name
                        if (
                            file_to_upload := convert_to_rntuple(output_path)
                        ) is not None:
                            output_path.unlink()
                    else:
                        file_to_upload = output_path
                        object_name = output_path.name

                if file_to_upload is not None:
                    # only None if conversion has failed
                    rec = FileCompleteRecord(
                        request_id=request_id,
                        file_path=_file_path,
                        s3_object_name=object_name,
                        file_id=file_id,
                        status="success",
                        total_time=time.time() - total_time,
                        total_events=transformer_stats.total_events,
                        total_bytes=file_to_upload.stat().st_size,
                    )
                    if object_store:
                        upload_file(file_to_upload, servicex, rec)
                    else:
                        servicex.put_file_complete(rec)

                    transform_success = True
                    logger.info("Transformer stats.", extra=log_extra)
                    science_container.confirm()
                    break
                else:
                    transform_success = False
                    transformer_stats.error_info = "Sidecar format conversion failed"

            science_container.confirm()

        # If none of the replicas resulted in a successful transform then we have
        # a hard failure with this file.
        if not transform_success:
            hf = {
                **log_extra,
                "input_path": _file_paths[0],
                "log_body": transformer_stats.log_body,
            }
            logger.error(f"Hard Failure: {transformer_stats.error_info}", extra=hf)

        if not transform_success:
            rec = FileCompleteRecord(
                request_id=request_id,
                file_path=_file_paths[0],
                file_id=file_id,
                s3_object_name="none",
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
                **log_extra,
                "user": elapsed_times.user,
                "sys": elapsed_times.system,
                "iowait": elapsed_times.iowait,
            },
        )

    except ScienceContainerException as e:
        logger.exception(
            "Science container not responding. Shutting down this transformer.",
            extra=log_extra,
            exc_info=e,
        )
        sys.exit(-1)

    except Exception as error:
        logger.exception(
            "Received exception doing transform", extra=log_extra, exc_info=error
        )
        rec = FileCompleteRecord(
            request_id=request_id,
            file_path=_file_paths[0],
            s3_object_name="none",
            file_id=file_id,
            status="failure",
            total_time=time.time() - total_time,
            total_events=0,
            total_bytes=0,
        )
        servicex.put_file_complete(rec)


def upload_file(
    source_path: Path, servicex: ServiceXAdapter, rec: FileCompleteRecord
) -> None:
    object_store = ObjectStoreManager()
    object_name = rec.s3_object_name

    logger.info(
        "Uploading file to object store.",
        extra={
            "request_id": request_id,
            "file_id": rec.file_id,
            "place": PLACE,
            "object_name": object_name,
        },
    )
    t0 = time.time()
    try:
        object_store.upload_file(request_id, object_name, source_path.as_posix())
        logger.info(
            "File uploaded to object store.",
            extra={
                "request_id": request_id,
                "file_id": rec.file_id,
                "place": PLACE,
                "object_name": object_name,
                "elapsed": time.time() - t0,
            },
        )

        servicex.put_file_complete(rec)

    except ObjectStoreError as e:
        logger.error(
            f"Error uploading file to object store: {e}",
            extra={
                "request_id": request_id,
                "place": PLACE,
                "file_id": rec.file_id,
                "object_name": object_name,
            },
        )
        rec.status = "failure"
        servicex.put_file_complete(rec)


def read_capabilities_file() -> dict[str, str]:
    """Wait for the capabilities file in the shared dir, and read it."""
    return _read_capabilities_file(shared_dir)


def init(args: Union[Namespace, SimpleNamespace], app: Celery) -> None:
    global convert_root_to_parquet, convert_root_to_rntuple, startup_time
    global object_store, posix_path, science_container
    global shared_dir, transformer_capabilities, request_id, celery_app

    shared_dir = args.shared_dir
    request_id = args.request_id
    celery_app = app

    # Stamps the id onto records whose call site can't supply one - everything
    # logged by celery.* and friends. This has to happen before worker_main()
    # below, which is where celery tears down and re-runs logging setup.
    set_request_id(request_id)

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
    # Same for rntuple
    convert_root_to_rntuple = (
        args.result_format == "root-rntuple"
        and "root-rntuple" not in transformer_capabilities["file-formats"]
    )

    startup_time = get_process_info()
    logger.info(
        "Startup finished.",
        extra={
            "request_id": request_id,
            "user": startup_time.user,
            "sys": startup_time.system,
            "iowait": startup_time.iowait,
            "place": PLACE,
        },
    )

    science_container = ScienceContainerCommand(request_id=request_id)
    logger.debug(
        "Connected to science container",
        extra={"request_id": request_id, "place": PLACE},
    )

    app.worker_main(
        argv=[
            "worker",
            "--concurrency=1",  # Don't allow multiple files to be processed at once
            "--without-mingle",
            "--without-gossip",
            "--without-heartbeat",
            "--loglevel=info",
            "-Q",
            f"transformer-{args.request_id}",
            "-n",
            f"transformer-{args.request_id}@%h",
        ]
    )


@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """
    Set the log level for the logger to INFO
    """
    initialize_logging(logger)


if __name__ == "__main__":  # pragma: no cover
    start_time = timeit.default_timer()

    parser = TransformerArgumentParser(description="ServiceX Transformer")
    _args = parser.parse_args()
    app = Celery("transformer_sidecar", broker=_args.rabbit_uri)
    app.conf.task_queues = [
        kombu.Queue(
            name=f"transformer-{_args.request_id}",
            durable=False,
            auto_delete=True,
            queue_arguments={"x-consumer-timeout": 2_629_746_000},
        )
    ]
    app.conf.task_create_missing_queues = False
    app.conf.worker_hijack_root_logger = True
    app.conf.worker_redirect_stdouts_level = "INFO"
    app.conf.worker_prefetch_multiplier = 1
    app.conf.broker_connection_retry_on_startup = True
    init(_args, app)

    logger.debug(
        "Shutting down transformer",
        extra={"request_id": request_id, "place": PLACE},
    )
    science_container.close()

    exit(0)
