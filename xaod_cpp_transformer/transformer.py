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
import logstash
import os
import time
from collections import namedtuple
import re

import psutil
# import uproot

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager
# from servicex.transformer.uproot_events import UprootEvents
# from servicex.transformer.uproot_transformer import UprootTransformer
# from servicex.transformer.arrow_writer import ArrowWriter


MAX_RETRIES = 3

messaging = None
object_store = None
posix_path = None

instance = os.environ.get('INSTANCE_NAME', 'Unknown')

# needs a downgrade for python2.7
# class StreamFormatter(logging.Formatter):
#     """
#     A custom formatter that adds extras.
#     Normally log messages are "level instance component msg extra: {}"
#     """
#     def_keys = ['name', 'msg', 'args', 'levelname', 'levelno',
#                 'pathname', 'filename', 'module', 'exc_info',
#                 'exc_text', 'stack_info', 'lineno', 'funcName',
#                 'created', 'msecs', 'relativeCreated', 'thread',
#                 'threadName', 'processName', 'process', 'message']

#     def format(self, record):
#         """
#         :param record: LogRecord
#         :return: formatted log message
#         """

#         string = super().format(record)
#         extra = {k: v for k, v in record.__dict__.items()
#                  if k not in self.def_keys}
#         if len(extra) > 0:
#             string += " extra: " + str(extra)
#         return string


class LogstashFormatter(logstash.formatter.LogstashFormatterBase):

    def format(self, record):
        message = {
            '@timestamp': self.format_timestamp(record.created),
            '@version': '1',
            'message': record.getMessage(),
            'host': self.host,
            'path': record.pathname,
            'tags': self.tags,
            'type': self.message_type,
            'instance': instance,
            'component': 'uproot transformer',

            # Extra Fields
            'level': record.levelname,
            'logger_name': record.name,
        }

        # Add extra fields
        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        if record.exc_info:
            message.update(self.get_debug_fields(record))

        return self.serialize(message)


def initialize_logging():
    """
    Get a logger and initialize it so that it outputs the correct format

    :param request: Request id to insert into log messages
    :return: logger with correct formatting that outputs to console
    """

    log = logging.getLogger()
    log.level = getattr(logging, os.environ.get('LOG_LEVEL'), 20)

    # stream_handler = logging.StreamHandler()
    # stream_formatter = logging.Formatter('%(levelname)s ' +
    #                                      "{} {} ".format(instance, os.environ["INSTANCE"]) +
    #                                      '%(message)s')
    # stream_formatter = StreamFormatter('%(levelname)s ' +
    #                                    instance + " xaod_transformer " +
    #                                    '%(message)s')
    # stream_handler.setFormatter(stream_formatter)
    # stream_handler.setLevel(log.level)
    # log.addHandler(stream_handler)

    logstash_host = os.environ.get('LOGSTASH_HOST')
    logstash_port = os.environ.get('LOGSTASH_PORT')
    if (logstash_host and logstash_port):
        logstash_handler = logstash.TCPLogstashHandler(logstash_host, logstash_port, version=1)
        logstash_formatter = LogstashFormatter('logstash', None, None)
        logstash_handler.setFormatter(logstash_formatter)
        logstash_handler.setLevel(log.level)
        log.addHandler(logstash_handler)

    log.info("Initialized logging")

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
        # logger.info("{} events processed out of {} total events".format(
        #     events_processed, total_events))
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


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_paths = transform_request['paths'].split(',')
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    logger.info("To transform", extra={'fpath': _file_paths,
                                       'requestId': _request_id, 'fileId': _file_id})
    servicex = ServiceXAdapter(_server_endpoint)

    if not os.path.isdir(posix_path):
        os.makedirs(posix_path)

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
                logger.info("Starting transformation.", extra={
                            'attempt': attempt, 'fpath': _file_path,
                            'requestId': _request_id, 'fileId': _file_id
                            })

                root_file = _file_path.replace('/', ':')

                output_path = os.path.join(posix_path, root_file)

                stime = time.time()
                (total_events, output_size) = transform_single_file(
                    _file_path, output_path, servicex)
                ttime = time.time()

                if object_store:
                    object_store.upload_file(_request_id, root_file, output_path)
                    os.remove(output_path)
                utime = time.time()

                servicex.put_file_complete(_file_path, _file_id, "success",
                                           num_messages=0,
                                           total_time=total_time,
                                           total_events=total_events,
                                           total_bytes=output_size)
                logger.info("Attempt succesful.",
                            extra={
                                'attempt': attempt,
                                'requestId': _request_id, 'fileId': _file_id,
                                'transform_time': round(ttime-stime, 3),
                                'upload_time': round(utime-ttime, 3)
                            })
                file_done = True
                break

            except Exception as error:
                file_retries += 1
                logger.warning("Transformation failed.",
                               extra={
                                   'attempt': attempt, 'fpath': _file_path,
                                   'requestId': _request_id, 'fileId': _file_id,
                                   'error': error
                               })

        if file_done:
            break

    if not file_done:
        channel.basic_publish(exchange='transformation_failures',
                              routing_key=_request_id + '_errors',
                              body=json.dumps(transform_request))
        servicex.put_file_complete(file_path=_file_path, file_id=_file_id,
                                   status='failure', num_messages=0, total_time=0,
                                   total_events=0, total_bytes=0)

    stop_process_info = get_process_info()
    elapsed_times = TimeTuple(user=stop_process_info.user - start_process_info.user,
                              system=stop_process_info.system - start_process_info.system,
                              iowait=stop_process_info.iowait - start_process_info.iowait)

    logger.info("File processed.", extra={
        'requestId': _request_id, 'fileId': _file_id,
        'output-size': output_size,
        'events': total_events,
        'user': elapsed_times.user,
        'sys': elapsed_times.system,
        'iowait': elapsed_times.iowait
    })

    channel.basic_ack(delivery_tag=method.delivery_tag)


def transform_single_file(file_path, output_path, servicex=None):
    """
    Transform a single file and return some information about output

    :param file_path: path for file to process
    :param output_path: path to file
    :param servicex: servicex instance
    :return: Tuple with (total_events: Int, output_size: Int)
    """

    stime = time.time()
    r = os.system('bash /generated/runner.sh -r -d ' + file_path +
                  ' -o ' + output_path + '| tee log.txt')
    # This command is not available in all images!
    # os.system('/usr/bin/sync log.txt')
    ttime = time.time()

    total_events, _ = parse_output_logs("log.txt")
    output_size = 0
    if os.path.exists(output_path) and os.path.isfile(output_path):
        output_size = os.stat(output_path).st_size
        # logger.info("Wrote {} bytes after transforming {}".format(output_size, file_path))

    wtime = time.time()
    logger.info('Detailed transformer times.', extra={
        'query_time': round(ttime - stime, 3),
        'parsing_log': round(wtime - ttime, 3)
    })
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

    return total_events, output_size


def compile_code():
    # Have to use bash as the file runner.sh does not execute properly, despite its 'x'
    # bit set. This seems to be some vagary of a ConfigMap from k8, which is how we usually get
    # this file.
    r = os.system('bash /generated/runner.sh -c | tee log.txt')
    if r != 0:
        with open('log.txt', 'r') as f:
            errors = f.read()
            logger.error("Unable to compile the code - error return: " +
                         str(r) + 'errors: ' + errors)
            raise RuntimeError("Unable to compile the code - error return: " +
                               str(r) + "errors: \n" + errors)


if __name__ == "__main__":
    parser = TransformerArgumentParser(description=os.environ["DESC"])
    args = parser.parse_args()

    logger = initialize_logging()

    if args.output_dir:
        object_store = None
    if args.result_destination == 'object-store':
        posix_path = "/home/atlas"
        object_store = ObjectStoreManager()
    elif args.result_destination == 'volume':
        object_store = None
        posix_path = args.output_dir

    compile_code()
    startup_time = get_process_info()
    logger.info("Startup finished.",
                extra={
                    'user': startup_time.user, 'sys': startup_time.system,
                    'iowait': startup_time.iowait
                })

    if args.request_id and not args.path:
        rabbitmq = RabbitMQManager(args.rabbit_uri, args.request_id, callback)

    if args.path:
        logger.info("Transform a single file", extra={'fpath': args.path})
        transform_single_file(args.path, args.output_dir)
