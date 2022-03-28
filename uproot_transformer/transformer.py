# Copyright (c) 2019, IRIS-HEP
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
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import json
import logging
import os
import sys
import time
import timeit
from collections import namedtuple
import re

import psutil
import uproot
import awkward as ak

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
# from servicex.transformer.arrow_writer import ArrowWriter
from hashlib import sha1
import pyarrow.parquet as pq

# Needed until we use xrootd>=5.2.0
# see https://github.com/ssl-hep/ServiceX_Uproot_Transformer/issues/22
uproot.open.defaults["xrootd_handler"] = uproot.MultithreadedXRootDSource

MAX_RETRIES = 3

object_store = None
posix_path = None
MAX_PATH_LEN = 255


def initialize_logging(request=None):
    """
    Get a logger and initialize it so that it outputs the correct format

    :param request: Request id to insert into log messages
    :return: logger with correct formatting that outputs to console
    """

    log = logging.getLogger()
    if 'INSTANCE_NAME' in os.environ:
        instance = os.environ['INSTANCE_NAME']
    else:
        instance = 'Unknown'
    formatter = logging.Formatter('%(levelname)s ' +
                                  "{} uproot_transformer {} ".format(instance, request) +
                                  '%(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


def parse_output_logs(logfile):
    """
    Parse output from runner.sh and output appropriate log messages
    :param logfile: path to logfile
    :return:  Tuple with (total_events: Int, processed_events: Int)
    """
    total_events = 0
    events_processed = 0
    total_events_re = re.compile(r'Processing events \d+-(\d+)')
    events_processed_re = re.compile(r'Processed (\d+) events')
    with open(logfile, 'r') as f:
        buf = f.read()
        match = total_events_re.search(buf)
        if match:
            total_events = int(match.group(1))
        matches = events_processed_re.finditer(buf)
        for m in matches:
            events_processed = int(m.group(1))
        logger.info("{} events processed out of {} total events".format(
            events_processed, total_events))
    return total_events, events_processed


class TimeTuple(namedtuple("TimeTupleInit", ["user", "system", "iowait"])):
    """
    Named tuple to store process time information.
    Immutable so values can't be accidentally altered after creation
    """
    # user: float
    # system: float
    # iowait: float

    @property
    def total_time(self):
        """
        Return total time spent by process

        :return: sum of user, system, iowait times
        """
        return self.user + self.system + self.iowait


def get_process_info():
    """
    Get process information (just cpu, sys, iowait times right now) and return it

    :return: TimeTuple with timing information
    """
    process_info = psutil.Process()
    time_stats = process_info.cpu_times()
    return TimeTuple(user=time_stats.user+time_stats.children_user,
                     system=time_stats.system+time_stats.children_system,
                     iowait=time_stats.iowait)


def log_stats(startup_time, elapsed_time, running_time=0.0):
    """
    Log statistics about transformer execution

    :param startup_time: time to initialize and run cpp transformer
    :param elapsed_time:  elapsed time spent by processing file (sys, user, iowait)
    :param running_time:  total time to run script
    :return: None
    """
    logger.info("Startup process times  user: {} sys: {} ".format(startup_time.user,
                                                                  startup_time.system) +
                "iowait: {} total: {}".format(startup_time.iowait, startup_time.total_time))
    logger.info("File processing times  user: {} sys: {} ".format(elapsed_time.user,
                                                                  elapsed_time.system) +
                "iowait: {} total: {}".format(elapsed_time.iowait, elapsed_time.total_time))
    logger.info("Total running time {}".format(running_time))


class ArrowIterator:
    def __init__(self, arrow, file_path):
        self.arrow = arrow
        self.file_path = file_path
        self.attr_name_list = ["not available"]

    def arrow_table(self):
        yield self.arrow


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
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_paths = transform_request['paths'].split(',')
    logger.info("File replicas: {}".format(_file_paths))
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    servicex = ServiceXAdapter(_server_endpoint)

    servicex.post_status_update(file_id=_file_id,
                                status_code="start",
                                info="Starting")

    tick = time.time()

    file_done = False
    file_retries = 0
    total_events = 0
    output_size = 0
    total_time = 0
    start_process_info = get_process_info()
    for attempt in range(MAX_RETRIES):
        for _file_path in _file_paths:
            try:

                # Do the transform
                logger.info("Attempt {}. Trying path {}".format(attempt, _file_path))
                root_file = _file_path.replace('/', ':')
                if not os.path.isdir(posix_path):
                    os.makedirs(posix_path)

                safe_output_file = hash_path(root_file+".parquet")
                output_path = os.path.join(posix_path, safe_output_file)

                (total_events, output_size) = transform_single_file(
                    _file_path, output_path, servicex)

                tock = time.time()
                total_time = round(tock - tick, 2)
                if object_store:
                    object_store.upload_file(_request_id, safe_output_file, output_path)
                    os.remove(output_path)

                servicex.post_status_update(file_id=_file_id,
                                            status_code="complete",
                                            info="Total time " + str(total_time))
                servicex.put_file_complete(_file_path, _file_id, "success",
                                           num_messages=0,
                                           total_time=total_time,
                                           total_events=0,
                                           total_bytes=0)
                logger.info("Time tos process {}: {} seconds".format(
                    root_file, total_time))
                file_done = True
                break

            except Exception as error:
                file_retries += 1
                logger.warning("Failed attempt {} of {} for {}: {}".format(attempt,
                                                                           MAX_RETRIES,
                                                                           root_file,
                                                                           error))
                servicex.post_status_update(file_id=_file_id,
                                            status_code="retry",
                                            info="Try: " + str(file_retries) +
                                            " error: " + str(error)[0:1024])

        if file_done:
            break

    if not file_done:
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))
        servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                   status='failure', num_messages=0, total_time=0,
                                   total_events=0, total_bytes=0)
        servicex.post_status_update(file_id=_file_id,
                                    status_code="failure",
                                    info="error.")

    stop_process_info = get_process_info()
    elapsed_process_times = TimeTuple(user=stop_process_info.user - start_process_info.user,
                                      system=stop_process_info.system - start_process_info.system,
                                      iowait=stop_process_info.iowait - start_process_info.iowait)
    stop_time = timeit.default_timer()
    log_stats(startup_time, elapsed_process_times, running_time=(stop_time - start_time))
    record = {'filename': _file_path,
              'file-id': _file_id,
              'output-size': output_size,
              'events': total_events,
              'request-id': _request_id,
              'user-time': elapsed_process_times.user,
              'system-time': elapsed_process_times.system,
              'io-wait': elapsed_process_times.iowait,
              'total-time': elapsed_process_times.total_time,
              'wall-time': total_time}
    logger.info("Metric: {}".format(json.dumps(record)))
    channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path, servicex=None):
    """
    Transform a single file and return some information about output

    :param file_path: path for file to process
    :param output_path: path to file
    :param servicex: servicex instance
    :return: Tuple with (total_events: Int, output_size: Int)
    """
    logger.info(f"Transforming a single path: {file_path} into {output_path}")

    try:
        import generated_transformer
        start_transform = time.time()
        awkward_array = generated_transformer.run_query(file_path)
        end_transform = time.time()
        total_events = 0  # need to make this size of the array...
        logger.info('Ran generated_transformer.py in ' +
                    f'{round(end_transform - start_transform, 2)} sec')

        start_serialization = time.time()
        explode_records = bool(awkward_array.fields)
        try:
            arrow = ak.to_arrow_table(awkward_array, explode_records=explode_records)
        except TypeError:
            arrow = ak.to_arrow_table(ak.repartition(awkward_array, None),
                                      explode_records=explode_records)
        end_serialization = time.time()
        serialization_time = round(end_serialization - start_serialization, 2)
        logger.info(f'awkward Array -> Arrow in {serialization_time} sec')

        if output_path:
            writer = pq.ParquetWriter(output_path, arrow.schema)
            writer.write_table(table=arrow)
            writer.close()
            output_size = os.stat(output_path).st_size
            logger.info("Wrote {} bytes after transforming {}".format(output_size, file_path))

    except Exception as error:
        mesg = f"Failed to transform input file {file_path}: {error}"
        logger.exception(mesg)
        raise RuntimeError(mesg)
    return total_events, output_size


def compile_code():
    # import generated_transformer
    pass


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="Uproot Transformer")
    args = parser.parse_args()

    logger = initialize_logging(args.request_id)
    logger.info(f"sys.path: {sys.path}")
    logger.info(f"result destination: {args.result_destination}  output dir: {args.output_dir}")

    if args.output_dir:
        object_store = None
    if args.result_destination == 'object-store':
        posix_path = "/home/output"
        object_store = ObjectStoreManager()
    elif args.result_destination == 'volume':
        object_store = None
        posix_path = args.output_dir

    compile_code()
    startup_time = get_process_info()

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        logger.info("Transform a single file ", args.path)
        transform_single_file(args.path, args.output_dir)
