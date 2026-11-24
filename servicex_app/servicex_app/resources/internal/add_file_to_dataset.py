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

from servicex_app.models import TransformRequest, db
from servicex_app.orchestrator_mode import use_temporal
from servicex_app.resources.servicex_resource import ServiceXResource

from servicex_app.dataset_manager import DatasetManager


class AddFileToDataset(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        try:
            # this request can be a single file dictionary or a list of file
            # dictionaries. Files are upserted on file_key (the Temporal DID finder
            # worker sends the Rucio scope:name; without one the first path is the
            # key), so a retried lookup updates rows instead of duplicating them.
            add_file_request = request.get_json()
            dataset_manager = DatasetManager.from_dataset_id(
                dataset_id, current_app.logger, db
            )

            # check if the response is bulk or single file
            if type(add_file_request) is dict:
                add_file_request = [add_file_request]

            current_app.logger.info(
                f"Adding {len(add_file_request)} files to dataset: {dataset_manager.name}",
                extra={"dataset_id": dataset_id},
            )

            if use_temporal(current_app.config):
                # The request workflows dispatch files and keep requests.files; the
                # app only records them.
                files = dataset_manager.upsert_files(add_file_request)
            else:
                # find running requests that need this ds.
                running_requests = TransformRequest.lookup_running_by_dataset_id(
                    dataset_id
                )
                files = dataset_manager.add_files(
                    add_file_request, running_requests, self.lookup_result_processor
                )
            # The Temporal DID finder worker signals this to the dataset lookup
            # workflow as the high-water mark of files available to transform.
            # Updated rows count too, so a retry that re-sends only existing files
            # still reports the right mark.
            max_file_id = max((f.id for f in files), default=0)
            db.session.commit()

            return {"dataset_id": str(dataset_id), "max_file_id": max_file_id}
        except Exception as e:
            current_app.logger.exception(
                "Exception occurred when adding file to dataset",
                extra={"dataset_id": dataset_id},
            )
            return {"message": f"Something went wrong: {e}"}, 500
