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
from transformer_sidecar.object_store_manager import ObjectStoreManager
import uproot
import awkward as ak


class ObjectStoreUploader(threading.Thread):
    class WorkQueueItem:
        def __init__(self, source_path: Path):
            self.source_path = source_path

        def is_complete(self):
            return not self.source_path

    def __init__(self, request_id: str,
                 input_queue: Queue,
                 object_store: ObjectStoreManager,
                 logger: logging.Logger,
                 result_format: str,
                 transformer_format: str):
        super().__init__(target=self.service_work_queue)
        self.request_id = request_id
        self.input_queue = input_queue
        self.object_store = object_store
        self.logger = logger
        self.result_format = result_format
        self.transformer_format = transformer_format

    def parquet_to_root(self, item):
        print("Path: ", str(item.source_path))
        print("Name: ", item.source_path.name)
        with uproot.open(Path(item.source_path)) as data:
            for tree in data.keys():
                tree_data = data[tree].arrays(library='ak')
                ak.to_parquet(tree_data, item.source_path)

    def service_work_queue(self):
        while True:
            item = self.input_queue.get()
            self.logger.debug("Got an item", extra={'requestId': self.request_id})
            if item.is_complete():
                self.logger.debug("We are done", extra={'requestId': self.request_id})
                break
            else:
                if self.result_format == "parquet" and self.transformer_format == "root":
                    self.parquet_to_root(item)
                    self.object_store.upload_file(self.request_id,
                                                  item.source_path.name,
                                                  str(item.source_path))
                else:
                    self.object_store.upload_file(self.request_id,
                                                  item.source_path.name,
                                                  str(item.source_path))
