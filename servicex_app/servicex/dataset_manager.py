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
from logging import Logger
from typing import List

from flask_sqlalchemy import SQLAlchemy
from servicex.did_parser import DIDParser
from servicex.lookup_result_processor import LookupResultProcessor
from servicex.models import Dataset, DatasetFile, TransformRequest, DatasetStatus


class DatasetManager:
    def __init__(self, dataset: Dataset, logger: Logger, db: SQLAlchemy):
        self.dataset = dataset
        self.did = None if dataset.did_finder == 'user' else DIDParser(dataset.name)
        self.logger = logger
        self.db = db

        self.logger.debug(f"DatasetManager: {self.dataset.name}")

    @classmethod
    def from_did(cls, did: DIDParser, logger: Logger, extras: dict[str, str] = None,
                 db: SQLAlchemy = None):
        # This removes wrongly implemented subset of file selection
        clean_did = did.full_did.split('?')[0]
        dataset = Dataset.find_by_name(clean_did)
        if not dataset:
            dataset = Dataset(
                name=clean_did,
                last_used=datetime.now(tz=timezone.utc),
                last_updated=datetime.fromtimestamp(0),
                lookup_status=DatasetStatus.created,
                did_finder=did.scheme
            )
            dataset.save_to_db()
            logger.info(f"Created new dataset: {dataset.name}, id is {dataset.id}",
                        extra=extras)
        else:
            logger.info(f"Found existing dataset: {dataset.name}, id is {dataset.id}",
                        extra=extras)
        return cls(dataset, logger, db)

    @classmethod
    def file_list_hash(cls, file_list: List[str]):
        return hashlib.sha256(" ".join(file_list).encode()).hexdigest()

    @classmethod
    def from_file_list(cls, file_list: List[str], logger: Logger,
                       extras: dict[str, str] = None,
                       db: SQLAlchemy = None):
        name = cls.file_list_hash(file_list)
        dataset = Dataset.find_by_name(name)

        if not dataset:
            dataset = Dataset(
                name=name,
                last_used=datetime.now(tz=timezone.utc),
                last_updated=datetime.fromtimestamp(0),
                lookup_status=DatasetStatus.complete,
                did_finder='user',
                files=[
                    DatasetFile(
                        paths=file,
                        adler32="xxx",
                        file_events=0,
                        file_size=0
                    ) for file in file_list
                ]
            )

            dataset.save_to_db()
            logger.info(f"Created new dataset for file list. Dataset Id is {dataset.id}",
                        extra=extras)
        else:
            logger.info(f"Found existing dataset for file list. Dataset Id is {dataset.id}",
                        extra=extras)

        return cls(dataset, logger, db)

    @classmethod
    def from_dataset_id(cls, dataset_id: int, logger: Logger, db: SQLAlchemy):
        dataset = Dataset.find_by_id(dataset_id)
        if not dataset:
            raise RuntimeError(f"Could not find dataset with id {dataset_id}")
        return cls(dataset, logger, db)

    @property
    def name(self):
        if self.did:
            return self.did.full_did
        else:
            return self.file_list_hash(self.file_paths)

    @property
    def id(self):
        return self.dataset.id

    @property
    def is_lookup_required(self) -> bool:
        """
        Report whether a submission to a DID finder is called for. Thid is true if the
        dataset is not complete and the lookup status is not 'looking'
        """
        return self.dataset.lookup_status not in [DatasetStatus.looking, DatasetStatus.complete]

    @property
    def is_complete(self) -> bool:
        return self.dataset.lookup_status == DatasetStatus.complete

    @property
    def file_paths(self) -> List[str]:
        return [file.paths for file in self.dataset.files]

    def refresh(self):
        self.db.session.refresh(self.dataset)

    def submit_lookup_request(self, advertised_endpoint, rabbitmq_adaptor):
        did_request = {
            "dataset_id": self.dataset.id,
            "did": self.did.did,
            "endpoint": advertised_endpoint
        }
        rabbitmq_adaptor.basic_publish(exchange='',
                                       routing_key=self.did.microservice_queue,
                                       body=json.dumps(did_request))

        self.dataset.lookup_status = DatasetStatus.looking

    def publish_files(self, request: TransformRequest,
                      lookup_result_processor: LookupResultProcessor) -> None:
        request.files = len(self.dataset.files)
        lookup_result_processor.add_files_to_processing_queue(request, files=[
            file for file in self.dataset.files
        ])

    def add_files(self, files: List[DatasetFile], requests: List[TransformRequest],
                  lookup_result_processor: LookupResultProcessor) -> None:
        self.dataset.files.extend(files)
        self.dataset.save_to_db()

        for request in requests:
            request.files += len(files)
            lookup_result_processor.add_files_to_processing_queue(request, files=[
                file for file in files
            ])
            request.save_to_db()
