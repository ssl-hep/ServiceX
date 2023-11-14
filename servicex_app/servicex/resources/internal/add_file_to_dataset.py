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

from servicex.models import DatasetFile, TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource

from servicex.dataset_manager import DatasetManager


class AddFileToDataset(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        try:
            # this request can be a single file dictionary
            # or a list of file dictionaries.
            add_file_request = request.get_json()
            dataset_manager = DatasetManager.from_dataset_id(dataset_id, current_app.logger, db)

            # find running requests that need this ds.
            running_requests = TransformRequest.lookup_running_by_dataset_id(dataset_id)

            # check if the request is bulk or single file
            if type(add_file_request) is dict:
                add_file_request = [add_file_request]

            current_app.logger.info(
                f"Adding {len(add_file_request)} files to dataset: {dataset_manager.name}",
                extra={'dataset_id': dataset_id})

            # See if there are any requests based on this dataset that were submitted
            # after the triggering request. We need to catch them up with the list of
            # files reported up to now
            for running_request in running_requests:
                if running_request.status == "Submitted":
                    dataset_manager.publish_files(running_request, self.lookup_result_processor)
                    running_request.files = dataset_manager.dataset.n_files
                    if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
                        self.transformer_manager.start_transformers(
                            current_app.config,
                            running_request
                        )

            new_files = [DatasetFile(dataset_id=dataset_id,
                                     paths=','.join(file['paths']),
                                     adler32=file['adler32'],
                                     file_events=file['file_events'],
                                     file_size=file['file_size']) for file in add_file_request]
            dataset_manager.add_files(new_files, running_requests, self.lookup_result_processor)
            db.session.commit()

            return {
                "dataset_id": str(dataset_id)
            }
        except Exception as e:
            current_app.logger.exception("Exception occurred when adding file to dataset",
                                         extra={'dataset_id': dataset_id})
            return {'message': f"Something went wrong: {e}"}, 500
