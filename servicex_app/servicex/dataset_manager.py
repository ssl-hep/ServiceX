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
import hashlib
import json
from datetime import datetime, timezone
from typing import List

from servicex.did_parser import DIDParser
from servicex.lookup_result_processor import LookupResultProcessor
from servicex.models import Dataset, DatasetFile, TransformRequest


class DatasetManager:
    def __init__(self, did: DIDParser = None, file_list: List[str] = None, dataset_id: int = None):
        """
        Create a dataset manager for a given dataset. The dataset can be specified either
        by a DID or a list of files. If a list of files is specified, the dataset name
        will be the SHA256 hash of the list of files.

        Raises:
            ValueError: If neither did nor file_list is specified or if both are specified
        """
        # Are we creating a new dataset or looking up an existing one?
        if dataset_id:
            self.dataset = Dataset.find_by_id(dataset_id)
            if not self.dataset:
                raise ValueError(f"Dataset with id {dataset_id} not found")
            self.did = DIDParser(self.dataset.name)

        else:
            if not (bool(did) ^ bool(file_list)):
                raise ValueError("Must specify either did or file_list")

            self.did = did
            self.file_list = file_list

            self.dataset = Dataset.find_by_name(self.name)

            if not self.dataset:
                self.dataset = Dataset(
                    name=self.name,
                    last_used=datetime.now(tz=timezone.utc),
                    last_updated=datetime.fromtimestamp(0),
                    lookup_status='created',
                    did_finder=self.did.scheme if self.did else 'user'
                )
                self.dataset.save_to_db()

                # If this is a new filelist we can go ahead and add the files to the dataset
                if self.file_list and self.dataset.lookup_status == 'created':
                    for file in file_list:
                        self.add_file(file)
                        self.dataset.lookup_status = "complete"

    def add_file(self, paths: str) -> None:
        file_record = DatasetFile(
            dataset_id=self.dataset.id,
            paths=paths,
            adler32="xxx",
            file_events=0,
            file_size=0
        )
        file_record.save_to_db()
        self.dataset.n_files = len(paths)
        self.dataset.lookup_status = 'complete'

    @property
    def name(self):
        if self.did:
            return self.did.full_did
        else:
            return hashlib.sha256(" ".join(self.file_list).encode()).hexdigest()

    @property
    def is_lookup_required(self) -> bool:
        """
        Report whether a submission to a DID finder is called for. This is true if the
        dataset is still in the 'created' state and a DID is specified (i.e. not a file
        list)
        """
        return self.dataset.lookup_status == "created" and self.did

    @property
    def is_complete(self) -> bool:
        return self.dataset.lookup_status == "complete"

    def submit_lookup_request(self, advertised_endpoint, rabbitmq_adaptor):
        did_request = {
            "dataset_id": self.dataset.id,
            "did": self.did.did,
            "endpoint": advertised_endpoint
        }
        rabbitmq_adaptor.basic_publish(exchange='',
                                       routing_key=self.did.microservice_queue,
                                       body=json.dumps(did_request))

        self.dataset.lookup_status = 'looking'

    def publish_files(self, request: TransformRequest,
                      lookup_result_processor: LookupResultProcessor) -> None:
        request.files = self.dataset.n_files
        lookup_result_processor.add_files_to_processing_queue(request, files=self.file_list)
