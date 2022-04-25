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
import logging
import os
import shutil
import sys
import time
import timeit
from typing import NamedTuple
import psutil as psutil

from servicex.transformer.servicex_adapter import ServiceXAdapter
from servicex.transformer.transformer_argument_parser import TransformerArgumentParser
from servicex.transformer.object_store_manager import ObjectStoreManager
from servicex.transformer.rabbit_mq_manager import RabbitMQManager

from queue import Queue
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

object_store = None
posix_path = None
FAILED = False
COMPLETED = False
TIMEOUT = 30


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
    formatter = logging.Formatter('%(levelname)s '
                                  + "{} transformer {} ".format(instance,
                                                                request)
                                  + '%(message)s')
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
    :param elapsed_time: elapsed time spent by processing file
                         (sys, user, iowait)
    :param running_time: total time to run script
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
    Get process information (just cpu, sys, iowait times right now) and
    return it

    :return: TimeTuple with timing information
    """
    process_info = psutil.Process()
    time_stats = process_info.cpu_times()
    return TimeTuple(user=time_stats.user + time_stats.children_user,
                     system=time_stats.system + time_stats.children_system,
                     iowait=time_stats.iowait)


# noinspection PyUnusedLocal
def callback(channel, method, properties, body):
    transform_request = json.loads(body)
    _request_id = transform_request['request-id']
    _file_path = transform_request['file-path']
    _file_id = transform_request['file-id']
    _server_endpoint = transform_request['service-endpoint']
    logger.info(transform_request)
    servicex = ServiceXAdapter(_server_endpoint)

    start_process_times = get_process_info()
    total_events = 0
    output_size = 0
    total_time = 0
    try:
        servicex.post_status_update(file_id=_file_id,
                                    status_code="start",
                                    info="Starting")

        if not os.path.isdir(posix_path):
            os.makedirs(posix_path)

        output_path = posix_path
        request_path = os.path.join(output_path, _request_id)
        # creating output dir for transform output files
        if not os.path.isdir(request_path):
            os.makedirs(request_path)
        # creating scripts dir for access by science transformer
        scripts_path = os.path.join(output_path, 'scripts')
        if not os.path.isdir(scripts_path):
            os.makedirs(scripts_path)
        shutil.copy('watch.sh', scripts_path)
        shutil.copy('proxy-exporter.sh',scripts_path)
        # creating json file for use by science transformer
        jsonfile = str(_file_id) + '.json'
        with open(os.path.join(request_path, jsonfile), 'w') as outfile:
            json.dump(transform_request, outfile)

        try:
            watch(logger,
                  request_path,
                  transform_request,
                  object_store=object_store,
                  servicex=servicex)
            global COMPLETED
            COMPLETED = False
        except Exception as e:
            global FAILED
            FAILED = True
            raise e

        shutil.rmtree(request_path)

        stop_process_times = get_process_info()
        user = stop_process_times.user - start_process_times.user
        system = stop_process_times.system - start_process_times.system
        iowait = stop_process_times.iowait - start_process_times.iowait
        elapsed_process_times = TimeTuple(user=user,
                                          system=system,
                                          iowait=iowait)

        stop_time = timeit.default_timer()
        log_stats(startup_time,
                  elapsed_process_times,
                  running_time=(stop_time - start_time))
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
                                   status='failure', num_messages=0,
                                   total_time=0, total_events=0,
                                   total_bytes=0)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def output_consumer(q, logger, transform_request, obj_store, servicex):
    while True:
        _request_id = transform_request['request-id']
        _file_path = transform_request['file-path']
        _file_id = transform_request['file-id']
        tick = time.time()
        item = q.get()
        filepath, filename = item.rsplit('/', 1)

        new_filename = _file_path.replace('/',':') + ':' + filename
        if obj_store:
            obj_store.upload_file(_request_id, new_filename, item)

        tock = time.time()
        total_time = round(tock - tick, 2)

        servicex.post_status_update(file_id=_file_id,
                                    status_code="complete",
                                    info="Success")

        servicex.put_file_complete(_file_path, _file_id, "success",
                                   num_messages=0,
                                   total_time=total_time,
                                   total_events=0,
                                   total_bytes=0)
        logger.info(
            "Time to successfully process {}: {} seconds".format(filepath, total_time))
        os.remove(item) 
        logger.info('Removed {fn} from directory.'.format(fn=item))
        q.task_done()

        timeout_start = time.time()
        while q.empty():
            if time.time() < timeout_start + TIMEOUT:
                time.sleep(1)
            else:
                logger.info('QUEUE is empty. Setting completed = True')
                global COMPLETED
                COMPLETED = True
                break
                            

class FileQueueHandler(FileSystemEventHandler):
    def __init__(self, logger, queue):
        self.logger = logger
        self.queue = queue

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            with open(event.src_path) as log:
                text = log.read()

            flags = ['exception', 'fatal']
            if any(flag in text.lower() for flag in flags):
                global FAILED
                FAILED = True

    def on_created(self, event):
        if not event.is_directory and not event.src_path.endswith('.log'):
            self.logger.info('File {fn} created.'.format(
                             fn=event.src_path))

            # check if file still being written, if not run upload
            while True:
                file_start = os.stat(event.src_path).st_size
                time.sleep(1)
                file_later = os.stat(event.src_path).st_size
                comp = file_later - file_start
                if comp == 0 and file_later != 0:
                    break
                else:
                    time.sleep(1)
            try:
                self.queue.put(event.src_path)
                self.logger.info(
                    'Added {fn} to queue.'.format(fn=event.src_path))
            except Exception as e:
                self.logger.exception(
                    'Failed to add file to queue {fn}: {e}'.format(fn=event.src_path, e=e))

def watch(logger, request_path,
          transform_request, 
          object_store=None, 
          servicex=None):
    # Start output queue
    q = Queue()

    # Initialize Observer
    observer = Observer()

    # Start consumer
    Thread(target=output_consumer,
           args=(q, logger, transform_request, object_store, servicex),
           daemon=True).start()

    # Initialize logging event handler
    event_handler = FileQueueHandler(logger, q)

    # Schedule Observer
    observer.schedule(event_handler, request_path, recursive=False)

    # Start the observer
    observer.start()
    
    while not (FAILED or COMPLETED):
        # Set the thread sleep time
        time.sleep(1)

    if COMPLETED:
        logger.info('Stopping observer. All work is done.')
        observer.stop()
        return
    
    if FAILED:
        logger.info('Stopping observer.')
        observer.stop()
        raise Exception('Transform failed...')

    observer.join()
    q.join()


if __name__ == "__main__":
    start_time = timeit.default_timer()
    parser = TransformerArgumentParser(description="ServiceX Transformer")
    args = parser.parse_args()

    logger = initialize_logging(args.request_id)
    logger.info("----- {}".format(sys.path))
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

    startup_time = get_process_info()

    if args.request_id:
        rabbitmq = RabbitMQManager(args.rabbit_uri,
                                   args.request_id,
                                   callback)
