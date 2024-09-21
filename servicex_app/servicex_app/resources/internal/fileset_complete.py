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
from flask import request, current_app

from servicex_app.models import Dataset, db, TransformRequest, TransformStatus, DatasetStatus
from servicex_app.resources.servicex_resource import ServiceXResource


class FilesetComplete(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        summary = request.get_json()
        dataset = Dataset.find_by_id(int(dataset_id))

        current_app.logger.info("Completed fileset for datasetID",
                                extra={'dataset_id': dataset_id,
                                       'elapsed-time': summary['elapsed-time']})
        dataset.n_files = summary['files']
        dataset.events = summary['total-events']
        dataset.size = summary['total-bytes']
        dataset.lookup_status = DatasetStatus.complete
        db.session.commit()

        if summary['files'] > 0:
            # Now time to pick up any transform requests for this dataset that came in
            # while we were still looking up files and send the dataset to them
            for transform_request in TransformRequest.lookup_pending_on_dataset(int(dataset_id)):
                dataset.publish_files(transform_request, self.lookup_result_processor)
                transform_request.status = TransformStatus.running

            # also resolve the status of whatever transform prompted this lookup
            for transform_request in \
                    TransformRequest.lookup_running_by_dataset_id(int(dataset_id)):
                transform_request.status = TransformStatus.running

        else:
            current_app.logger.info("No files found for datasetID. Shutting down transformers",
                                    extra={'dataset_id': dataset_id})

            # find running requests that needed this dataset and shut them down
            # there will never be any files
            namespace = current_app.config['TRANSFORMER_NAMESPACE']
            for running_request in TransformRequest.lookup_running_by_dataset_id(int(dataset_id)):
                running_request.status = TransformStatus.complete
                self.transformer_manager.shutdown_transformer_job(
                    running_request.request_id, namespace
                )

            # Tell any other transform that was waiting for the lookup to complete
            # not to expect to run
            for pending_transform in TransformRequest.lookup_pending_on_dataset(int(dataset_id)):
                pending_transform.status = TransformStatus.complete

        db.session.commit()
