# Copyright (c) 2022-5, IRIS-HEP
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
from datetime import datetime, timezone
from logging import Logger
from typing import List

from celery import Celery
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import insert
from servicex_app.did_parser import DIDParser
from servicex_app.lookup_result_processor import LookupResultProcessor
from servicex_app.models import Dataset, DatasetFile, TransformRequest, DatasetStatus


class DatasetManager:
    def __init__(self, dataset: Dataset, logger: Logger, db: SQLAlchemy):
        self.dataset = dataset
        self.did = None if dataset.did_finder == "user" else DIDParser(dataset.name)
        self.logger = logger
        self.db = db

        self.logger.debug(f"DatasetManager: {self.dataset.name}")

    @classmethod
    def from_did(
        cls,
        did: DIDParser,
        logger: Logger,
        db: SQLAlchemy,
        extras: dict[str, str] = {},
    ):
        dataset = Dataset.find_by_name_with_lock(
            did.full_did
        )  # strictly speaking, unnecessary
        if not dataset:
            dataset_timestamp = datetime.now(tz=timezone.utc)
            statement = (
                insert(Dataset)
                .values(
                    name=did.full_did,
                    last_used=dataset_timestamp,
                    last_updated=dataset_timestamp,
                    lookup_status=DatasetStatus.created,
                    did_finder=did.scheme,
                )
                .on_conflict_do_nothing()
            )
            db.session.execute(statement)
            dataset = Dataset.find_by_name_with_lock(did.full_did)
            assert dataset is not None, "Dataset {did.full_did} should exist"

            logger.info(
                f"Upserted dataset: {dataset.name}, id is {dataset.id}", extra=extras
            )
        else:
            logger.info(
                f"Found existing dataset: {dataset.name}, id is {dataset.id}",
                extra=extras,
            )
            dataset.last_used = datetime.now(tz=timezone.utc)
        db.session.add(dataset)
        return cls(dataset, logger, db)

    @classmethod
    def file_list_hash(cls, file_list: List[str]):
        return hashlib.sha256(" ".join(file_list).encode()).hexdigest()

    @classmethod
    def from_file_list(
        cls,
        file_list: List[str],
        logger: Logger,
        db: SQLAlchemy,
        extras: dict[str, str] = {},
    ):
        name = cls.file_list_hash(file_list)
        dataset = Dataset.find_by_name_with_lock(name)

        if not dataset:
            dataset_timestamp = datetime.now(tz=timezone.utc)
            statement = (
                insert(Dataset)
                .values(
                    name=name,
                    last_used=dataset_timestamp,
                    last_updated=dataset_timestamp,
                    lookup_status=DatasetStatus.complete,
                    did_finder="user",
                )
                .on_conflict_do_nothing()
            )
            db.session.execute(statement)
            dataset = Dataset.find_by_name_with_lock(name)
            assert dataset is not None, f"Dataset {name} should exist"

            # The path is the file's key. A path listed twice keys only its first
            # row (as the v1_10_0 backfill does); the repeat keeps NULL so it does
            # not violate UNIQUE(dataset_id, file_key).
            seen = set()
            dataset.files = []
            for file in file_list:
                dataset.files.append(
                    DatasetFile(
                        paths=file,
                        file_key=None if file in seen else file,
                        adler32="xxx",
                        file_events=0,
                        file_size=0,
                    )
                )
                seen.add(file)
            dataset.n_files = len(file_list)

            logger.info(
                f"Upserted dataset for file list. Dataset Id is {dataset.id}",
                extra=extras,
            )
        else:
            logger.info(
                f"Found existing dataset for file list. Dataset Id is {dataset.id}",
                extra=extras,
            )
            dataset.last_used = datetime.now(tz=timezone.utc)

        db.session.add(dataset)
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
        return self.dataset.lookup_status not in [
            DatasetStatus.looking,
            DatasetStatus.complete,
        ]

    @property
    def is_complete(self) -> bool:
        return self.dataset.lookup_status == DatasetStatus.complete

    @property
    def file_paths(self) -> List[str]:
        return [file.paths for file in self.dataset.files]

    def refresh(self):
        self.db.session.refresh(self.dataset)

    def submit_lookup_request(self, advertised_endpoint, celery_app: Celery):
        task_id = celery_app.send_task(
            f"{self.did.microservice_queue}.lookup_dataset",
            args=[self.did.did, self.dataset.id, advertised_endpoint],
        )

        self.logger.debug(
            f"Submitted lookup request for {self.did.did} taskID {task_id} "
        )
        self.mark_lookup_started()

    def mark_lookup_started(self) -> None:
        """Record that a DID finder lookup is under way, so later requests for this
        dataset wait for it instead of starting another."""
        self.dataset.lookup_status = DatasetStatus.looking

    def publish_files(
        self, request: TransformRequest, lookup_result_processor: LookupResultProcessor
    ) -> None:
        request.files = len(self.dataset.files)
        lookup_result_processor.add_files_to_processing_queue(
            request, files=[file for file in self.dataset.files]
        )

    def upsert_files(self, records: List[dict]) -> List[DatasetFile]:
        """Insert DID finder file records into this dataset, or update the row with
        the same file_key. Returns the inserted and updated rows, so a retried lookup
        that re-sends only existing files still reports their ids.

        Each record has paths (list of replicas), adler32, file_size, file_events and
        optionally file_key; a record without a key is keyed by its first path, as
        the DID finder lib and the v1_10_0 backfill do."""
        rows_by_key: dict = {}
        for record in records:
            file_key = record.get("file_key") or record["paths"][0]
            # Last one wins: Postgres refuses an ON CONFLICT DO UPDATE that would
            # touch the same row twice in one statement.
            rows_by_key[file_key] = {
                "dataset_id": self.dataset.id,
                "file_key": file_key,
                "paths": ",".join(record["paths"]),
                "adler32": record["adler32"],
                "file_size": record["file_size"],
                "file_events": record["file_events"],
            }
        if not rows_by_key:
            return []

        dialect = self.db.engine.dialect.name
        if dialect == "postgresql":
            dialect_insert = postgresql.insert
        elif dialect == "sqlite":
            dialect_insert = sqlite.insert
        else:
            raise RuntimeError(f"No upsert for database dialect {dialect}")

        statement = dialect_insert(DatasetFile).values(list(rows_by_key.values()))
        statement = statement.on_conflict_do_update(
            index_elements=["dataset_id", "file_key"],
            set_={
                column: statement.excluded[column]
                for column in ("paths", "adler32", "file_size", "file_events")
            },
        ).returning(DatasetFile)
        rows = list(
            self.db.session.scalars(
                statement, execution_options={"populate_existing": True}
            )
        )
        # The relationship collection does not see rows written by a Core-style
        # insert; reload it on next access.
        self.db.session.expire(self.dataset, ["files"])
        return rows

    def add_files(
        self,
        records: List[dict],
        requests: List[TransformRequest],
        lookup_result_processor: LookupResultProcessor,
    ) -> List[DatasetFile]:
        """Celery mode: upsert the files, then queue them for every running request."""
        files = self.upsert_files(records)
        # Commit before queueing, as before the upsert: a transformer must be able to
        # see a file's row by the time it reports on it.
        self.db.session.commit()

        for request in requests:
            request.files += len(files)
            lookup_result_processor.add_files_to_processing_queue(request, files=files)
            request.save_to_db()
        return files
