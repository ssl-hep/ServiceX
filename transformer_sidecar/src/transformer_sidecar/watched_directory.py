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
import logging
import os
import re
import time
from pathlib import Path
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from transformer_sidecar.servicex_adapter import ServiceXAdapter
from transformer_sidecar.object_store_uploader import ObjectStoreUploader
from enum import Enum


class WatchedDirectory:
    class TransformStatus(Enum):
        READY = 0
        RUNNING = 1
        SUCCESS = 2
        FAILURE = 3

    def __init__(self, path: Path, result_upload_queue: Queue,
                 logger: logging.Logger, servicex: ServiceXAdapter):
        self.path = path
        self.logger = logger
        self.observer = Observer()
        self.event_handler = TransformerEventHandler(result_upload_queue,
                                                     logger,
                                                     servicex,
                                                     self)

        self.status = WatchedDirectory.TransformStatus.READY
        self.events = 0
        self.total_events = 0
        self.total_size = 0

    def start(self):
        self.observer.schedule(self.event_handler, str(self.path))
        self.status = WatchedDirectory.TransformStatus.RUNNING
        self.observer.start()

    def stop(self, success: bool):
        self.logger.info("Shutting down watched directory thread")
        self.observer.stop()
        self.status = WatchedDirectory.TransformStatus.SUCCESS \
            if success \
            else WatchedDirectory.TransformStatus.FAILURE


class TransformerEventHandler(FileSystemEventHandler):
    def __init__(self, result_upload_queue: Queue,
                 logger: logging.Logger,
                 servicex: ServiceXAdapter,
                 my_watched_directory: WatchedDirectory):
        self.result_upload_queue = result_upload_queue
        self.servicex = servicex
        self.logger = logger
        self.watched_directory = my_watched_directory

    def on_created(self, event):
        """
        This event is triggered whenever a new file is created. We assume that the writing
        of the transformer output file is pretty atomic. We do hang around and wait for
        the number of bytes to stop changing.

        We also handle .done file which is written to signal that the job is done
        """
        # Nothing to do on directory events or log files
        if event.is_directory or event.src_path.endswith('.log'):
            return

        # Look for signal that the job is done
        if event.src_path.endswith(".done"):
            self.watched_directory.stop(success=True)

            # Terminate the upload thread too
            self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(None))
            return

        if event.src_path.endswith(".failed"):
            self.watched_directory.stop(success=False)

            # Terminate the upload thread too
            self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(None))
            return

        self.logger.info('File {fn} created.'.format(fn=event.src_path))

        # check if file still being written/copied
        while True:
            file_start = os.stat(event.src_path).st_size
            time.sleep(1)
            file_later = os.stat(event.src_path).st_size
            comp = file_later - file_start
            if comp == 0 and file_later != 0:
                break
            else:
                time.sleep(1)

        self.watched_directory.total_size = os.stat(event.src_path).st_size

        # add file to queue for upload
        try:
            self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(Path(event.src_path)))
            self.logger.info(
                'Added {fn} to queue.'.format(fn=event.src_path))
        except Exception as e:
            self.logger.exception(
                'Failed to add file to queue {fn}: {e}'.format(fn=event.src_path, e=e))
            self.watched_directory.stop(success=False)

            # Terminate the upload thread too
            self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(None))

    def on_modified(self, event):
        if event.is_directory:
            return

        # if *.log file detected read file
        if event.src_path.endswith('.log'):
            with open(event.src_path) as log:
                text = log.read()

            # scan for flag keywords and skip any further log file analysis if found
            keywords = ['fatal', 'runtimeerror']
            if any(flag in text.lower() for flag in keywords):
                self.logger.error(text)
                self.logger.error('Found exception. Exiting.')
                return

            # look for event counts, set to 0 if not found
            try:
                matches = re.findall(
                    r'[\d\s]+events processed out of[\d\s]+total events', text)

                if matches:
                    events, total_events = re.findall(r'[\d]+', matches[0])
                    print(f"Events {events}, totalEvents {total_events}")
                    if (int(events) == 0) or (int(total_events) == 0):
                        self.watched_directory.status = WatchedDirectory.TransformStatus.FAILURE
                        self.logger.info(
                            "Failed to process all events: {num}/{den}".format(num=events,
                                                                               den=total_events))
                    else:
                        self.watched_directory.total_events = int(total_events)
                        self.watched_directory.events = int(events)

            except Exception as eek:
                self.logger.exception("Exception processing log file", eek)