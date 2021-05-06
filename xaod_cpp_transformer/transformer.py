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
import re
import time

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
from servicex.transformer.uproot_events import UprootEvents
from servicex.transformer.uproot_transformer import UprootTransformer
from servicex.transformer.arrow_writer import ArrowWriter
import uproot
import os
import sys

import logging
import timeit
import psutil
# from typing import NamedTuple
from collections import namedtuple


# How many bytes does an average awkward array cell take up. This is just
# a rule of thumb to calculate chunksize
avg_cell_size = 42
MAX_RETRIES = 3

messaging = None
object_store = None


def initialize_logging(request=None):
    """
    Get a logger and initialize it so that it outputs the correct format

    :param request: Request id to insert into log messages
    :return: logger with correct formatting that outputs to console
    """

    log = logging.getLogger()
    instance = os.environ.get('INSTANCE_NAME', 'Unknown')
    formatter = logging.Formatter('%(levelname)s ' +
                                  "{} xaod_cpp_transformer {} ".format(instance, request) +
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
        logger.info("{} events processed out of {} total events".format(events_processed, total_events))
    return total_events, events_processed

# class TimeTuple(NamedTuple):
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


def log_stats(startup_time, total_time, running_time=0.0):
    """
    Log statistics about transformer execution

    :param startup_time: time to initialize and run cpp transformer
    :param total_time:  total process times (sys, user, iowait)
    :param running_time:  total time to run script
    :return: None
    """
    logger.info("Startup process times  user: {} sys: {} ".format(startup_time.user,
                                                                  startup_time.system) +
                "iowait: {} total: {}".format(startup_time.iowait, startup_time.total_time))
    logger.info("Total process times  user: {} sys: {} ".format(total_time.user,
                                                                total_time.system) +
                "iowait: {} total: {}".format(total_time.iowait, total_time.total_time))
    logger.info("Total running time {}".format(running_time))


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_path = transform_request['file-path'].encode('ascii', 'ignore')
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    _chunks = transform_request['chunk-size']
    servicex = ServiceXAdapter(_server_endpoint)

    servicex.post_status_update(file_id=_file_id,
                                status_code="start",
                                info="xAOD Transformer")

    tick = time.time()

    time_info1 = get_process_info()
    time_info2 = get_process_info()
    logger.info("*********** Time test")
    log_stats(time_info1, time_info2, 0)
    p = psutil.Process()
    logger.info("Time info 1: {}".format(p.cpu_times()))
    logger.info("Time info 2: {}".format(p.cpu_times()))

    file_done = False
    file_retries = 0
    total_events = 0
    output_size = 0
    total_time = 0
    while not file_done:
        try:
            # Do the transform
            root_file = _file_path.replace('/', ':')
            output_path = '/home/atlas/' + root_file
            logger.info("Processing {}, file id: {}".format(root_file, _file_id))
            (total_events, output_size) = transform_single_file(_file_path, output_path, _chunks, servicex)

            tock = time.time()
            total_time = round(tock - tick, 2)
            if object_store:
                object_store.upload_file(_request_id, root_file, output_path)
                os.remove(output_path)

            servicex.post_status_update(file_id=_file_id,
                                        status_code="complete",
                                        info="Total time " + str(total_time))
            servicex.put_file_complete(_file_path, _file_id, "success",
                                       num_messages=0,
                                       total_time=round(tock - tick, 2),
                                       total_events=total_events,
                                       total_bytes=output_size)
            logger.info("Time to successfully process {}: {} seconds".format(root_file, total_time))
            file_done = True

        except Exception as error:
            file_retries += 1
            if file_retries == MAX_RETRIES:
                transform_request['error'] = str(error)
                channel.basic_publish(exchange='transformation_failures',
                                      routing_key=_request_id + '_errors',
                                      body=json.dumps(transform_request))
                servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                           status='failure', num_messages=0, total_time=total_time,
                                           total_events=total_events, total_bytes=output_size)

                servicex.post_status_update(file_id=_file_id,
                                            status_code="failure",
                                            info="error: " + str(error))

                file_done = True
                exc_type, exc_value, exc_traceback = sys.exc_info()
                logger.exception("Received exception")
            else:
                servicex.post_status_update(file_id=_file_id,
                                            status_code="retry",
                                            info="Try: " + str(file_retries) +
                                                 " error: " + str(error)[0:1024])

    total_time = get_process_info()
    stop_time = timeit.default_timer()
    log_stats(startup_time, total_time, running_time=(stop_time - start_time))

    channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path, chunks, servicex=None):
    """
    Transform a single file and return some information about output

    :param file_path: path for file to process
    :param output_path: path to file
    :param chunks: size of chunk
    :param servicex: servicex instance
    :return: Tuple with (total_events: Int, output_size: Int)
    """

    logger.info("Transforming a single path: " + str(file_path) + " into " + output_path)
    # os.system("voms-proxy-info --all")
    r = os.system('bash /generated/runner.sh -r -d ' + file_path + ' -o ' + output_path + '| tee log.txt')
    os.system('/usr/bin/sync log.txt')
    total_events, _ = parse_output_logs("log.txt")
    output_size = 0
    if os.path.exists(output_path) and os.path.isfile(output_path):
        output_size = os.stat(output_path).st_size
        logger.info("Wrote {} bytes after transforming {}".format(output_size, file_path))

    reason_bad = None
    if r != 0:
        reason_bad = "Error return from transformer: " + str(r)
    if (reason_bad is None) and not os.path.exists(output_path):
        reason_bad = "Output file " + output_path + " was not found"
    if reason_bad is not None:
        with open('log.txt', 'r') as f:
            errors = f.read()
            mesg = "Failed to transform input file {}: ".format(file_path) + \
                   "{} -- errors: {}".format(reason_bad, errors)
            logger.error(mesg)
            raise RuntimeError(mesg)

    if not object_store:
        flat_file = uproot.open(output_path)
        flat_tree_name = flat_file.keys()[0]
        attr_name_list = flat_file[flat_tree_name].keys()

        arrow_writer = ArrowWriter(file_format=args.result_format,
                                   object_store=object_store,
                                   messaging=messaging)
        # NB: We're converting the *output* ROOT file to Arrow arrays
        event_iterator = UprootEvents(file_path=output_path, tree_name=flat_tree_name,
                                      attr_name_list=attr_name_list, chunk_size=chunks)
        transformer = UprootTransformer(event_iterator)
        arrow_writer.write_branches_to_arrow(transformer=transformer, topic_name=args.request_id,
                                             file_id=None, request_id=args.request_id)
        logger.info("Kafka Timings: "+str(arrow_writer.messaging_timings))
    return total_events, output_size


def compile_code():
    # Have to use bash as the file runner.sh does not execute properly, despite its 'x'
    # bit set. This seems to be some vagary of a ConfigMap from k8, which is how we usually get
    # this file.
    r = os.system('bash /generated/runner.sh -c | tee log.txt')
    if r != 0:
        with open('log.txt', 'r') as f:
            errors = f.read()
            logger.error("Unable to compile the code - error return: " + str(r) + 'errors: ' + errors)
            raise RuntimeError("Unable to compile the code - error return: " + str(r) + "errors: \n" + errors)


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="xAOD CPP Transformer")
    args = parser.parse_args()

    logger = initialize_logging(args.request_id)

    if args.result_destination == 'kafka':
        msg = "Kafka is no longer supported as a transport mechanism"
        logger.error(msg)
        sys.stderr.write(msg + "\n")
    elif not args.output_dir and args.result_destination == 'object-store':
        messaging = None
        object_store = ObjectStoreManager()

    compile_code()
    startup_time = get_process_info()
    total_time = get_process_info()
    stop_time = timeit.default_timer()
    log_stats(startup_time, total_time, running_time=(stop_time - start_time))

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        transform_single_file(args.path, args.output_dir)
