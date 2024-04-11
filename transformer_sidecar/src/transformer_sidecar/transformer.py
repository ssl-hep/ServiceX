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

import time

import json
import os
import psutil as psutil
import shutil
import timeit
from hashlib import sha1, sha256
from pathlib import Path
from queue import Queue
from typing import NamedTuple

import socket

from object_store_manager import ObjectStoreManager
from object_store_uploader import ObjectStoreUploader
from rabbit_mq_manager import RabbitMQManager
from servicex_adapter import ServiceXAdapter
from transformer_argument_parser import TransformerArgumentParser
from transformer_sidecar.transformer_logging import initialize_logging
from transformer_sidecar.transformer_stats import TransformerStats
from transformer_sidecar.transformer_stats.aod_stats import AODStats  # NOQA: 401
from transformer_sidecar.transformer_stats.uproot_stats import UprootStats  # NOQA: 401

object_store = None
posix_path = None
startup_time = None
convert_root_to_parquet = False

serv = None
conn = None
upload_queue = None

# Use this to make sure we don't generate output file names that are crazy long
MAX_PATH_LEN = 255

PLACE = {
    "host_name": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown")
}


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


def get_process_info():
    """
    Get process information (just cpu, sys, iowait times right now) and
    return it

    :return: TimeTuple with timing information
    """
    process_info = psutil.Process()
    time_stats = process_info.cpu_times()
    return TimeTuple(user=time_stats.user + time_stats.children_user,
                     system=time_stats.system + time_stats.children_system,
                     iowait=time_stats.iowait)


def hash_path(file_name):
    """
    Make the path safe for object store or POSIX, by keeping the length
    less than MAX_PATH_LEN. Replace the leading (less interesting) characters with a
    forty character hash.
    :param file_name: Input filename
    :return: Safe path string
    """
    if len(file_name) > MAX_PATH_LEN:
        hash = sha1(file_name.encode('utf-8')).hexdigest()
        return ''.join([
            '_', hash,
            file_name[-1 * (MAX_PATH_LEN - len(hash) - 1):],
        ])
    else:
        return file_name


def fill_stats_parser(stats_parser_name: str, logfile_path: Path) -> TransformerStats:
    # Assume that the stats parser class has been imported
    return globals()[stats_parser_name](logfile_path)


def prepend_xcache(file_paths):
    # if CACHE_PREFIX is not given, returns file paths unchanged.

    prefix = os.environ.get('CACHE_PREFIX', '')
    if not prefix:
        return file_paths

    # One could have a single or multiple nodes in CACHE_PREFIX
    # If multiple are given, they must be comma separated.
    # In case of multiple xcaches, we want a given file to always be prepended
    # with the same xcache.

    # split the string into a list of xcaches. strip in case someone adds spaces
    xcs = [p.strip() for p in prefix.split(',')]

    prefixed_paths = []
    for f in file_paths:

        # for each path we get an integer hash
        hex_digest = sha256(f.encode()).hexdigest()

        # we turn file hex_digest into an integer then calculate module of the
        # value.
        c = int(hex_digest, 16) % len(xcs)

        # we should have xcaches listed without "root:// //" and
        prefixed_paths.append(f'root://{xcs[c]}//{f}')
    return prefixed_paths

# noinspection PyUnusedLocal


def callback(channel, method, properties, body):
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
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']

    # If we are converting root to parquet here, then the transformer
    # doesn't need to know about. Tell it to write root, and we'll take it from here
    if convert_root_to_parquet:
        transform_request['result-format'] = 'root'

    # The transform can either include a single path, or a list of replicas
    if 'file-path' in transform_request:
        _file_paths = [transform_request['file-path']]

        # make sure that paths starting with http are at the end of the list
        _https = []
        _roots = []
        for _fp in _file_paths:
            if _fp.startswith('http'):
                _https.append(_fp)
            else:
                _roots.append(_fp)
        _file_paths = _roots+_https
    else:
        _file_paths = transform_request['paths'].split(',')

    # adding cache prefix
    _file_paths = prepend_xcache(_file_paths)

    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    logger.info("got transform request.", extra={
        "requestId": _request_id,
        "paths": _file_paths,
        "result-destination": transform_request['result-destination'],
        "result-format": transform_request['result-format'],
        "service-endpoint": transform_request['service-endpoint'],
        "place": PLACE
    })
    servicex = ServiceXAdapter(_server_endpoint)

    # creating output dir for transform output files
    request_path = os.path.join(posix_path, _request_id)
    os.makedirs(request_path, exist_ok=True)

    # scratch dir where the transformer temporarily writes the results.
    scratch_path = os.path.join(posix_path, _request_id, 'scratch')
    os.makedirs(scratch_path, exist_ok=True)

    start_process_info = get_process_info()
    total_time = time.time()

    transform_success = False
    try:
        # Loop through the replicas
        for _file_path in _file_paths:
            logger.info("trying to transform file", extra={
                        "requestId": _request_id, "file-path": _file_path, "place": PLACE})

            # Enrich the transform request to give more hints to the science container
            transform_request['downloadPath'] = _file_path

            # Decide an optional file extension for the results. If the output format is
            # parquet then we add that as an extension, otherwise stick with the format
            # of the input file.
            result_extension = ".parquet" \
                if transform_request['result-format'] == 'parquet' \
                else ""
            hashed_file_name = hash_path(_file_path.replace('/', ':') + result_extension)

            # The transformer will write results here as they are generated. This
            # directory isn't monitored.
            transform_request['safeOutputFileName'] = os.path.join(
                scratch_path,
                hashed_file_name
            )

            while True:
                print('waiting for the GeT')
                req = conn.recv(4096)
                if not req:
                    print('problem in getting GeT')
                    break
                req1 = req.decode('utf8')
                print("REQ >>>>>>>>>>>>>>>", req1)
                if req1.startswith('GeT'):
                    break

            res = json.dumps(transform_request)+"\n"
            print("sending:", res)
            conn.send(res.encode())

            print('WAITING FOR STATUS...')
            req = conn.recv(4096)
            if not req:
                break
            req2 = req.decode('utf8').strip()
            print('STATUS RECEIVED :', req2)
            logger.info(f"received result: {req2}", extra={
                        "requestId": _request_id, "file-path": _file_path, "place": PLACE})

            if req2 == 'success.':
                logger.info("adding item to OSU queue", extra={
                            "requestId": _request_id, "file-path": _file_path,
                            "place": PLACE})
                upload_queue.put(ObjectStoreUploader.WorkQueueItem(
                    Path(transform_request['safeOutputFileName'])))
            conn.send("confirmed.\n".encode())

            # Grab the logs
            transformer_stats = fill_stats_parser(
                transformer_capabilities['stats-parser'],
                Path(os.path.join(request_path, 'abc.log'))
            )

            if req2 == 'success.':
                transform_success = True
                ts = {
                    "requestId": _request_id,
                    "log_body": transformer_stats.log_body,
                    "file-size": transformer_stats.file_size,
                    "total-events": transformer_stats.total_events,
                    "place": PLACE
                }
                logger.info("Transformer stats.", extra=ts)
                break

        # If none of the replicas resulted in a successful transform then we have
        # a hard failure with this file.
        if not transform_success:
            hf = {
                "requestId": _request_id,
                "file-id": _file_id,
                "error-info": transformer_stats.error_info,
                "log_body": transformer_stats.log_body,
                "place": PLACE
            }
            logger.error("Hard Failure", extra=hf)

        if transform_success:
            servicex.put_file_complete(_request_id, _file_path, _file_id, "success",
                                       total_time=time.time()-total_time,
                                       total_events=transformer_stats.total_events,
                                       total_bytes=transformer_stats.file_size
                                       )
        else:
            servicex.put_file_complete(_request_id, file_path=_file_path, file_id=_file_id,
                                       status='failure',
                                       total_time=time.time()-total_time, total_events=0,
                                       total_bytes=0)

        stop_process_info = get_process_info()
        elapsed_times = TimeTuple(user=stop_process_info.user - start_process_info.user,
                                  system=stop_process_info.system - start_process_info.system,
                                  iowait=stop_process_info.iowait - start_process_info.iowait)

        logger.info("File processed.", extra={
            'requestId': _request_id, 'fileId': _file_id,
            'user': elapsed_times.user,
            'sys': elapsed_times.system,
            'iowait': elapsed_times.iowait,
            "place": PLACE
        })

    except Exception as error:
        logger.exception(f"Received exception doing transform: {error}")

        transform_request['error'] = str(error)
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))

        servicex.put_file_complete(_request_id, file_path=_file_paths[0], file_id=_file_id,
                                   status='failure',
                                   total_time=time.time()-total_time, total_events=0,
                                   total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="ServiceX Transformer")
    args = parser.parse_args()

    logger = initialize_logging()
    logger.info("tranformer startup", extra={"result_destination": args.result_destination,
                "output dir": args.output_dir, "place": PLACE})

    if args.output_dir:
        object_store = None
    if args.result_destination == 'object-store':
        posix_path = "/servicex/output"
        object_store = ObjectStoreManager()
    elif args.result_destination == 'volume':
        object_store = None
        posix_path = args.output_dir
    elif args.output_dir:
        object_store = None

    os.makedirs(posix_path, exist_ok=True)

    # creating scripts dir for access by science container
    scripts_path = os.path.join(posix_path, 'scripts')
    os.makedirs(scripts_path, exist_ok=True)
    shutil.copy('watch.sh', scripts_path)
    shutil.copy('proxy-exporter.sh', scripts_path)

    logger.debug("Waiting for capabilities file")
    capabilities_file_path = Path(os.path.join(posix_path, 'transformer_capabilities.json'))
    while not capabilities_file_path.is_file():
        time.sleep(1)

    with open(capabilities_file_path) as capabilities_file:
        transformer_capabilities = json.load(capabilities_file)

    logger.debug('transformer capabilities', extra=transformer_capabilities)

    # If the user requested Parquet, but the transformer isn't capable of producing it,
    # then we will convert here....
    convert_root_to_parquet = args.result_format == 'parquet' and \
        'parquet' not in transformer_capabilities['file-formats']

    startup_time = get_process_info()
    logger.info("Startup finished.",
                extra={
                    'user': startup_time.user, 'sys': startup_time.system,
                    'iowait': startup_time.iowait, "place": PLACE
                })

    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.bind(('localhost', 8081))
    serv.listen()
    conn, addr = serv.accept()

    upload_queue = Queue()

    uploader = ObjectStoreUploader(request_id=args.request_id, input_queue=upload_queue,
                                   object_store=object_store, logger=logger,
                                   convert_root_to_parquet=convert_root_to_parquet)
    uploader.start()

    if args.request_id:
        rabbitmq = RabbitMQManager(args.rabbit_uri,
                                   args.request_id,
                                   callback)

    uploader.join()
    logger.info("Uploader is done", extra={'requestId': args.request_id, "place": PLACE})
