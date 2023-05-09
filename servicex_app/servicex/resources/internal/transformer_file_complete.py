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
from logging import Logger

from flask import request, current_app

from servicex import TransformerManager
from servicex.models import TransformRequest, TransformationResult, db
from servicex.resources.servicex_resource import ServiceXResource


class TransformerFileComplete(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager):
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, request_id):
        info = request.get_json()
        current_app.logger.info("FileComplete", extra={'requestId': request_id, 'metric': info})
        transform_req = TransformRequest.lookup(request_id)
        if transform_req is None:
            msg = f"Request not found with id: '{request_id}'"
            current_app.logger.error(msg, extra={'requestId': request_id})
            return {"message": msg}, 404

        if info['status'] == 'success':
            TransformRequest.file_transformed_successfully(request_id)
        else:
            TransformRequest.file_transformed_unsuccessfully(request_id)

        rec = TransformationResult(
            did=transform_req.did,
            request_id=request_id,
            file_path=info['file-path'],
            transform_status=info['status'],
            transform_time=info['total-time'],
            total_bytes=info['total-bytes'],
            total_events=info['total-events'],
            avg_rate=info['avg-rate']
        )
        rec.save_to_db()

        current_app.logger.info("FileComplete", extra={
            'requestId': request_id,
            'files_remaining': transform_req.files_remaining,
            'files_completed': transform_req.files_completed,
            'files_failed': transform_req.files_failed
        })
        files_remaining = transform_req.files_remaining
        if files_remaining is not None and files_remaining == 0:
            self.transform_complete(current_app.logger, transform_req, self.transformer_manager)
        return "Ok"

    @staticmethod
    def transform_complete(logger: Logger, transform_req: TransformRequest,
                           transformer_manager: TransformerManager):
        transform_req.status = "Complete"
        transform_req.finish_time = datetime.now(tz=timezone.utc)
        transform_req.save_to_db()
        db.session.commit()
        logger.info("Request completed. Shutting down transformers",
                    extra={'requestId': transform_req.request_id})
        namespace = current_app.config['TRANSFORMER_NAMESPACE']
        transformer_manager.shutdown_transformer_job(transform_req.request_id, namespace)
