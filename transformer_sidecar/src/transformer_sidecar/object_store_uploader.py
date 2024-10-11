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
import os
from multiprocessing import Process
from pathlib import Path
from queue import Queue
from typing import Optional

from transformer_sidecar.object_store_manager import ObjectStoreManager
from transformer_sidecar.servicex_adapter import ServiceXAdapter, FileCompleteRecord

PLACE = {
    "host_name": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown")
}


class WorkQueueItem:
    def __init__(self, source_path: Path,
                 servicex: ServiceXAdapter = None,
                 rec: FileCompleteRecord = None):
        self.source_path = source_path
        self.servicex = servicex
        self.rec = rec

    def is_complete(self):
        return not self.source_path


class ObjectStoreUploader(Process):

    def __init__(self, request_id: str, input_queue: Queue,
                 logger: logging.Logger,
                 convert_root_to_parquet: bool):
        super().__init__(target=self.service_work_queue)
        self.request_id = request_id
        self.input_queue = input_queue
        self.logger = logger
        self.convert_root_to_parquet = convert_root_to_parquet

    def service_work_queue(self):
        self.logger.debug("Object store uploader starting.",
                          extra={'requestId': self.request_id, "place": PLACE})

        # We have to create the object store manager here, because it's not safe to
        # create it in the main process and pass it to the child process.
        object_store = ObjectStoreManager()

        while True:
            item = self.input_queue.get()

            # When we receive the poison pill, we're done.
            if item.is_complete():
                self.logger.debug("Object store uploader done!",
                                  extra={'requestId': self.request_id, "place": PLACE})
                break
            else:
                # Now is the time to convert the file to parquet if that's what the user
                # requested, but our particular transformer doesn't support it.
                if self.convert_root_to_parquet:
                    file_to_upload = self.convert_to_parquet(item.source_path)
                    object_name = item.source_path.with_suffix(".parquet").name
                else:
                    file_to_upload = item.source_path
                    object_name = item.source_path.name

                self.logger.info("Uploading file to object store.",
                                 extra={'requestId': self.request_id, "place": PLACE,
                                        "objectName": object_name})
                object_store.upload_file(self.request_id, object_name, file_to_upload.as_posix())
                self.logger.info("File uploaded to object store.",
                                 extra={'requestId': self.request_id, "place": PLACE,
                                        "objectName": object_name})

                item.servicex.put_file_complete(item.rec)
                self.input_queue.task_done()

    def convert_to_parquet(self, source_path: Path) -> Optional[Path]:
        """
        Convert a ROOT file to Parquet.  Returns the path to the Parquet file if successful,
        """
        import uproot
        import awkward as ak

        self.logger.info("Converting ROOT to Parquet.")
        with uproot.open(source_path) as data:
            if len(data.keys()) != 1:
                self.logger.error(f"Expected one tree found {data.keys()}")
                return None

            try:
                tree_name = data.keys()[0]
                all_data = data[tree_name].arrays(library='ak')

                parquet_file = source_path.with_suffix(".parquet")

                # Save to temp file in same directory as parquet_file. The to_parquet
                # method doesn't plqy well with long paths.
                temp_file = Path(parquet_file.parent, "temp.parquet")
                ak.to_parquet(all_data, temp_file.as_posix())
                temp_file.rename(parquet_file)

            except Exception as e:
                self.logger.error(f"Failed to convert ROOT to Parquet: {e}")
                return None

            return parquet_file
