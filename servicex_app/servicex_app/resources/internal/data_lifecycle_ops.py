# Copyright (c) 2024, IRIS-HEP
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
from datetime import datetime
from typing import List

from flask import request, current_app
from sqlalchemy import select, exists
from sqlalchemy.orm import Session

from servicex_app import ObjectStoreManager
from servicex_app.models import TransformRequest, Dataset, db, TransformationResult, \
    DatasetFile
from servicex_app.resources.servicex_resource import ServiceXResource


class DataLifecycleOps(ServiceXResource):
    @classmethod
    def make_api(cls, object_store_manager):
        cls.object_store = object_store_manager

    @staticmethod
    def delete_expired_transforms(session: Session,
                                  object_store: ObjectStoreManager,
                                  cutoff_timestamp: datetime) -> List[str]:
        deleted_log = []

        with session.begin():
            expired_transforms = session.query(TransformRequest).filter(
                TransformRequest.submit_time <= cutoff_timestamp
            ).all()

        for transform in expired_transforms:
            with session.begin():
                # Delete all the results for this transform
                session.query(TransformationResult).filter_by(
                    request_id=transform.request_id).delete()

                # Delete the transformed files out of object store along with the bucket
                if object_store:
                    object_store.delete_bucket_and_contents(transform.request_id)

                # Delete the transform request
                session.delete(transform)

                deleted_log.append(f"{transform.submitter_name} - {transform.request_id}: {transform.title}")
        return deleted_log

    def delete_orphaned_datasets(self, session: Session):
        deleted_datasets = []

        with session.begin():
            # Use a subquery to find the transforms that are using this dataset
            subquery = (
                select(1)
                .where(TransformRequest.did_id == Dataset.id)
            )

            # And then use ~exist to narrow down to the datasets that are not being used
            query = (
                select(Dataset)
                .where(~exists(subquery))
            )
            orphaned_datasets = session.execute(query).scalars().all()

        for dataset in orphaned_datasets:
            with session.begin():
                session.query(DatasetFile).filter_by(
                    dataset_id=dataset.id).delete()

                session.delete(dataset)

                deleted_datasets.append(f"{dataset.name} - {dataset.id}")

        return deleted_datasets

    def post(self):
        """
        Delete all data older than the given timestamp
        """

        # Start by deleting all the expired transforms
        cutoff_timestamp = datetime.fromisoformat(request.args['cutoff_timestamp'])
        deleted_log = self.delete_expired_transforms(
            session=db.session,
            object_store=self.object_store,
            cutoff_timestamp=cutoff_timestamp)

        if deleted_log:
            current_app.logger.info("Deleted expired transforms", extra={'deleted': deleted_log})
        else:
            current_app.logger.info("No expired transforms found")

        # Now lets see if there are any orphaned datasets and delete them
        deleted_datasets = self.delete_orphaned_datasets(db.session)

        if deleted_datasets:
            current_app.logger.info("Deleted orphaned datasets", extra={'deleted': deleted_datasets})
        else:
            current_app.logger.info("No orphaned datasets found")

        return {'deleted_transforms': deleted_log, 'deleted_datasets': deleted_datasets}
