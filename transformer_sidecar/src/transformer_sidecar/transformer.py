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
import psutil as psutil
import shutil
import timeit
from hashlib import sha1
from pathlib import Path
from queue import Queue
from typing import NamedTuple

from object_store_manager import ObjectStoreManager
from object_store_uploader import ObjectStoreUploader
from rabbit_mq_manager import RabbitMQManager
from servicex_adapter import ServiceXAdapter
from transformer_argument_parser import TransformerArgumentParser
from transformer_sidecar.transformer_logging import initialize_logging
from watched_directory import WatchedDirectory

object_store = None
posix_path = None
startup_time = None

# Use this to make sure we don't generate output file names that are crazy long
MAX_PATH_LEN = 255


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


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    """
    This is the main function for the transformer. It is called whenever a new message
    is available on the rabbit queue. These messages represent a single file to be
    transformed.

    Each request may include a list of replicas to try. This service will loop through
    the replicas and produce a json file for the science package to actually work from.
    This control file will have the replica for it to try to transform along with a
    path in the output directory for the generated parquet or root file to be written.

    This json file is written to the shared volume and then a thread is kicked off to
    wait for the json file to be deleted, which is the science package's way of showing
    it is done with the request. There will either be a parquet/root file in the output
    directory or at least a log file.

    We will examine this log file to see if the transform succeeded or failed
    """
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']

    # The transform can either include a single path, or a list of replicas
    if 'file-path' in transform_request:
        _file_paths = [transform_request['file-path']]
    else:
        _file_paths = transform_request['paths'].split(',')

    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    logger.info(transform_request)
    servicex = ServiceXAdapter(_server_endpoint)

    # creating output dir for transform output files
    request_path = os.path.join(posix_path, _request_id)
    os.makedirs(request_path, exist_ok=True)

    start_process_info = get_process_info()
    total_time = 0
    total_events = 0

    transform_success = False
    try:
        # Loop through the replicas
        for _file_path in _file_paths:
            logger.info(f"trying {_file_path}")
            servicex.post_status_update(file_id=_file_id,
                                        status_code="start",
                                        info="Starting")

            # Enrich the transform request to give more hints to the science container
            transform_request['downloadPath'] = _file_path

            # We want to sanitize the output file name - it should be tied to the input
            # file name, but they can be quite long, so we generate a hash for the boring
            # bits and chop them down as well as replacing shady characters.
            transform_request['safeOutputFileName'] = os.path.join(
                request_path,
                hash_path(
                    _file_path.replace('/', ':') +
                    ".parquet")
            )

            # creating json file for use by science transformer
            jsonfile = str(_file_id) + '.json'
            with open(os.path.join(request_path, jsonfile), 'w') as outfile:
                json.dump(transform_request, outfile)

            # Queue to communicate between WatchedDirectory and object file uploader
            upload_queue = Queue()

            # Watch for new files appearing in the shared directory
            watcher = WatchedDirectory(Path(request_path), upload_queue,
                                       logger=logger, servicex=servicex)

            # And upload them to the object store
            uploader = ObjectStoreUploader(request_id=_request_id, input_queue=upload_queue,
                                           object_store=object_store, logger=logger)

            watcher.start()
            uploader.start()

            # Wait for both threads to complete
            watcher.observer.join()
            logger.info(f"Watched Directory Thread is done. Status is {watcher.status}")
            uploader.join()
            logger.info("Uploader is done")

            # Grab the logs
            log_text = None
            with open(os.path.join(request_path, jsonfile + '.log')) as log:
                log_text = log.read()

            if watcher.status == WatchedDirectory.TransformStatus.SUCCESS:
                transform_success = True
                total_events = watcher.total_events
                logger.info(log_text)
                break

        logger.error(log_text)

        shutil.rmtree(request_path)

        if transform_success:
            servicex.post_status_update(file_id=_file_id,
                                        status_code="complete",
                                        info="Total time " + str(total_time))
            servicex.put_file_complete(_file_path, _file_id, "success",
                                       num_messages=0,
                                       total_time=total_time,
                                       total_events=total_events,
                                       total_bytes=0)
        else:
            servicex.post_status_update(file_id=_file_id,
                                        status_code="failure",
                                        info="error: Could not transform file")

            servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                       status='failure', num_messages=0,
                                       total_time=0, total_events=0,
                                       total_bytes=0)

        stop_process_info = get_process_info()
        elapsed_times = TimeTuple(user=stop_process_info.user - start_process_info.user,
                                  system=stop_process_info.system - start_process_info.system,
                                  iowait=stop_process_info.iowait - start_process_info.iowait)

        logger.info("File processed.", extra={
            'requestId': _request_id, 'fileId': _file_id,
            'user': elapsed_times.user,
            'sys': elapsed_times.system,
            'iowait': elapsed_times.iowait
        })

    except Exception as error:
        logger.exception(f"Received exception doing transform: {error}")

        transform_request['error'] = str(error)
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))

        servicex.post_status_update(file_id=_file_id,
                                    status_code="failure",
                                    info=f"error: {error}")

        servicex.put_file_complete(file_path=_file_paths[0], file_id=_file_id,
                                   status='failure', num_messages=0,
                                   total_time=0, total_events=0,
                                   total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="ServiceX Transformer")
    args = parser.parse_args()

    logger = initialize_logging()
    logger.info(f"result destination: {args.result_destination} \
                  output dir: {args.output_dir}")

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

    startup_time = get_process_info()
    logger.info("Startup finished.",
                extra={
                    'user': startup_time.user, 'sys': startup_time.system,
                    'iowait': startup_time.iowait
                })

    if args.request_id:
        rabbitmq = RabbitMQManager(args.rabbit_uri,
                                   args.request_id,
                                   callback)
