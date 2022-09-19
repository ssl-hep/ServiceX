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
from datetime import datetime, timezone

from flask import request, current_app

from servicex.models import TransformRequest, TransformationResult, DatasetFile, db
from servicex.resources.servicex_resource import ServiceXResource


class TransformerFileComplete(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager):
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, request_id):
        info = request.get_json()
        current_app.logger.info(f"Metric: {info}", extra={'requestId': request_id})
        transform_req = TransformRequest.lookup(request_id)
        if transform_req is None:
            msg = f"Request not found with id: '{request_id}'"
            current_app.logger.error(msg, extra={'requestId': request_id})
            return {"message": msg}, 404

        dataset_file = DatasetFile.get_by_id(info['file-id'])

        rec = TransformationResult(
            did=transform_req.did,
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

        # Commit here to avoid race condition with other file complete messages which
        # could result in miscounting completed files.
        db.session.commit()

        files_remaining = transform_req.files_remaining
        if files_remaining is not None and files_remaining == 0:
            namespace = current_app.config['TRANSFORMER_NAMESPACE']
            current_app.logger.info("Job is all done... shutting down transformers",
                                    extra={'requestId': request_id})
            self.transformer_manager.shutdown_transformer_job(request_id, namespace)
            transform_req.status = "Complete"
            transform_req.finish_time = datetime.now(tz=timezone.utc)
            transform_req.save_to_db()

        db.session.commit()

        return "Ok"
