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
import time
from enum import Enum
from pathlib import Path
from queue import Queue
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from transformer_sidecar.object_store_uploader import ObjectStoreUploader
from transformer_sidecar.servicex_adapter import ServiceXAdapter


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
            self.logger.info("Found a failiure. Bombing...")
            self.watched_directory.stop(success=False)

            # Terminate the upload thread too
            self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(None))
            return

        self.logger.info('File created.', extra={'file-path': event.src_path})

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
        self.result_upload_queue.put(ObjectStoreUploader.WorkQueueItem(Path(event.src_path)))
        self.logger.info(
            'Added file to upload queue.', extra={"file-path": event.src_path})
