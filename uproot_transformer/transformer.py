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
import time
import timeit
from typing import NamedTuple

import awkward as ak
import psutil as psutil
import uproot
import time

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.kafka_messaging import KafkaMessaging
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
from servicex.transformer.uproot_events import UprootEvents
from servicex.transformer.uproot_transformer import UprootTransformer
from servicex.transformer.arrow_writer import ArrowWriter
from hashlib import sha1
import os
import pyarrow.parquet as pq
import pyarrow as pa

# Needed until we use xrootd>=5.2.0 (see https://github.com/ssl-hep/ServiceX_Uproot_Transformer/issues/22)
uproot.open.defaults["xrootd_handler"] = uproot.MultithreadedXRootDSource

# How many bytes does an average awkward array cell take up. This is just
# a rule of thumb to calculate chunksize
avg_cell_size = 42

messaging = None
object_store = None
posix_path = None
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


class ArrowIterator:
    def __init__(self, arrow, chunk_size, file_path):
        self.arrow = arrow
        self.chunk_size = chunk_size
        self.file_path = file_path
        self.attr_name_list = ["not available"]

    def arrow_table(self):
        yield self.arrow


# function to initialize logging
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
    _file_path = transform_request['file-path']
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    # _chunks = transform_request['chunks']
    servicex = ServiceXAdapter(_server_endpoint)

    tick = time.time()
    start_process_times = get_process_info()
    total_events = 0
    output_size = 0
    total_time = 0
    try:
        # Do the transform
        servicex.post_status_update(file_id=_file_id,
                                    status_code="start",
                                    info="Starting")

        root_file = _file_path.replace('/', ':')
        if not os.path.isdir(posix_path):
            os.makedirs(posix_path)

        safe_output_file = hash_path(root_file+".parquet")
        output_path = os.path.join(posix_path, safe_output_file)
        transform_single_file(_file_path, output_path, servicex)

        tock = time.time()
        total_time = round(tock - tick, 2)
        if object_store:
            object_store.upload_file(_request_id, safe_output_file, output_path)
            os.remove(output_path)

        servicex.post_status_update(file_id=_file_id,
                                    status_code="complete",
                                    info="Success")

        servicex.put_file_complete(_file_path, _file_id, "success",
                                   num_messages=0,
                                   total_time=total_time,
                                   total_events=0,
                                   total_bytes=0)
        logger.info("Time to successfully process {}: {} seconds".format(root_file, total_time))
        stop_process_times = get_process_info()
        elapsed_process_times = TimeTuple(user=stop_process_times.user - start_process_times.user,
                                          system=stop_process_times.system - start_process_times.system,
                                          iowait=stop_process_times.iowait - start_process_times.iowait)
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

    except Exception as error:
        logger.exception(f"Received exception doing transform: {error}")

        transform_request['error'] = str(error)
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))

        servicex.post_status_update(file_id=_file_id,
                                    status_code="failure",
                                    info=f"error: {error}")

        servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                   status='failure', num_messages=0, total_time=0,
                                   total_events=0, total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path, servicex=None):
    logger.info(f"Transforming a single path: {file_path}")

    try:
        import generated_transformer
        start_transform = time.time()
        awkward_array = generated_transformer.run_query(file_path)
        end_transform = time.time()
        logger.info('Ran generated_transformer.py in ' +
                    f'{round(end_transform - start_transform, 2)} sec')

        start_serialization = time.time()
        explode_records = bool(awkward_array.fields)
        try:
            arrow = ak.to_arrow_table(awkward_array, explode_records=explode_records)
        except TypeError:
            arrow = ak.to_arrow_table(ak.repartition(awkward_array, None), explode_records=explode_records)
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

    if messaging:
        arrow_writer = ArrowWriter(file_format=args.result_format,
                                   object_store=None,
                                   messaging=messaging)

        # Todo implement chunk size parameter
        transformer = ArrowIterator(arrow, chunk_size=1000, file_path=file_path)
        arrow_writer.write_branches_to_arrow(transformer=transformer, topic_name=args.request_id,
                                             file_id=None, request_id=args.request_id)


def compile_code():
    import generated_transformer
    pass


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="Uproot Transformer")
    args = parser.parse_args()

    logger = initialize_logging(args.request_id)

    kafka_brokers = TransformerArgumentParser.extract_kafka_brokers(args.brokerlist)

    logger.info(f"result destination: {args.result_destination}  output dir: {args.output_dir}")
    if args.output_dir:
        messaging = None
        object_store = None
    if args.result_destination == 'kafka':
        messaging = KafkaMessaging(kafka_brokers, args.max_message_size)
        object_store = None
    elif args.result_destination == 'object-store':
        messaging = None
        posix_path = "/home/output"
        object_store = ObjectStoreManager()
    elif args.result_destination == 'volume':
        messaging = None
        object_store = None
        posix_path = args.output_dir
    elif args.output_dir:
        messaging = None
        object_store = None

    compile_code()
    startup_time = get_process_info()

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        logger.info("Transform a single file ", args.path)
        transform_single_file(args.path, args.output_dir)
