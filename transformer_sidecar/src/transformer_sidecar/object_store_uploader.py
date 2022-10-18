# Copyright (c) 2022, IRIS-HEP
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
import threading
from pathlib import Path
from queue import Queue
from servicex.transformer.object_store_manager import ObjectStoreManager


class ObjectStoreUploader(threading.Thread):
    class WorkQueueItem:
        def __init__(self, source_path: Path):
            self.source_path = source_path

        def get_filename(self):
            filepath, filename = self.source_path.rsplit('/', 1)

            # update filename
            new_filename = _file_path.replace('/', ':') + ':' + filename

        def is_complete(self):
            return not self.source_path

    def __init__(self, request_id: str,
                 input_queue: Queue,
                 object_store: ObjectStoreManager,
                 logger: logging.Logger):
        super().__init__(target=self.service_work_queue)
        self.request_id = request_id
        self.input_queue = input_queue
        self.object_store = object_store
        self.logger = logger

    def service_work_queue(self):
        while True:
            item = self.input_queue.get()
            self.logger.info("Got an item")
            if item.is_complete():
                self.logger.info("We are done")
                break
            else:
                self.object_store.upload_file(self.request_id, new_filename, item)

