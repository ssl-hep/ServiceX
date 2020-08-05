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

from servicex.models import TransformRequest, TransformationResult, DatasetFile, db
from servicex.resources.servicex_resource import ServiceXResource


class TransformerFileComplete(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager, elasticsearch_adapter):
        cls.transformer_manager = transformer_manager
        cls.elasticsearch_adapter = elasticsearch_adapter
        return cls

    def put(self, request_id):
        info = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)
        dataset_file = DatasetFile.get_by_id(info['file-id'])

        rec = TransformationResult(
            did=submitted_request.did,
            file_id=dataset_file.id,
            request_id=request_id,
            file_path=info['file-path'],
            transform_status=info['status'],
            transform_time=info['total-time'],
            total_bytes=info['total-bytes'],
            total_events=info['total-events'],
            avg_rate=info['avg-rate'],
            messages=info['num-messages']
        )
        rec.save_to_db()

        if self.elasticsearch_adapter:
            self.elasticsearch_adapter.create_update_path(
                dataset_file.get_path_id(),
                self._generate_file_status_record(dataset_file, info['status']))

            self.elasticsearch_adapter.create_update_request(
                request_id,
                self._generate_transformation_record(submitted_request, 'transforming'))

        files_remaining = TransformRequest.files_remaining(request_id)
        if files_remaining is not None and files_remaining <= 0:
            namespace = current_app.config['TRANSFORMER_NAMESPACE']
            print("Job is all done... shutting down transformers")
            self.transformer_manager.shutdown_transformer_job(request_id, namespace)
            submitted_request.status = "Complete"
            submitted_request.save_to_db()

            if self.elasticsearch_adapter:
                self.elasticsearch_adapter.create_update_request(
                    request_id,
                    self._generate_transformation_record(submitted_request, 'complete'))

        print(info)
        db.session.commit()

        return "Ok"
