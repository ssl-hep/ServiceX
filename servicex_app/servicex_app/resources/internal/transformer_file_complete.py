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
import logging
from datetime import datetime, timezone
from logging import Logger

from flask import request, current_app
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, \
    before_sleep_log, after_log

from servicex_app import TransformerManager
from servicex_app.models import TransformRequest, TransformationResult, db, TransformStatus
from servicex_app.resources.servicex_resource import ServiceXResource
import time


class TransformerFileComplete(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager):
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, request_id):
        start_time = time.time()
        info = request.get_json()
        logger = current_app.logger
        logger.info("FileComplete", extra={'requestId': request_id, 'metric': info})
        transform_req = self.record_file_complete(current_app.logger, request_id, info)

        if transform_req is None:
            return "Request not found", 404

        self.save_transform_result(transform_req, info)

        files_remaining = transform_req.files_remaining
        if files_remaining is not None and files_remaining == 0:
            self.transform_complete(current_app.logger, transform_req, self.transformer_manager)

        current_app.logger.info("FileComplete. Request state.", extra={
            'requestId': request_id,
            'files_remaining': transform_req.files_remaining,
            'files_completed': transform_req.files_completed,
            'files_failed': transform_req.files_failed,
            'report_processed_time': (time.time() - start_time)
        })
        return "Ok"

    @staticmethod
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential_jitter(initial=0.1, max=30),
           before_sleep=before_sleep_log(current_app.logger, logging.INFO),
           after=after_log(current_app.logger, logging.INFO),
           )
    def record_file_complete(logger: Logger, request_id: str, info: dict[str, str]) -> TransformRequest | None:
        transform_req = TransformRequest.lookup(request_id)
        if transform_req is None:
            msg = f"Request not found with id: '{request_id}'"
            logger.error(msg, extra={'requestId': request_id})
            return None

        if info['status'] == 'success':
            TransformRequest.file_transformed_successfully(request_id)
        else:
            TransformRequest.file_transformed_unsuccessfully(request_id)

        return transform_req

    @staticmethod
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential_jitter(initial=0.1, max=30),
           before_sleep=before_sleep_log(current_app.logger, logging.INFO),
           after=after_log(current_app.logger, logging.INFO),
           )
    def save_transform_result(transform_req: TransformRequest, info: dict[str, str]):
        rec = TransformationResult(
            did=transform_req.did,
            file_id=info['file-id'],
            request_id=transform_req.request_id,
            file_path=info['file-path'],
            transform_status=info['status'],
            transform_time=info['total-time'],
            total_bytes=info['total-bytes'],
            total_events=info['total-events'],
            avg_rate=info['avg-rate']
        )
        rec.save_to_db()
        db.session.commit()

    @staticmethod
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential_jitter(initial=0.1, max=30),
           before_sleep=before_sleep_log(current_app.logger, logging.INFO),
           after=after_log(current_app.logger, logging.INFO),
           )
    def transform_complete(logger: Logger, transform_req: TransformRequest,
                           transformer_manager: TransformerManager):
        transform_req.status = TransformStatus.complete
        transform_req.finish_time = datetime.now(tz=timezone.utc)
        transform_req.save_to_db()
        db.session.commit()
        logger.info("Request completed. Shutting down transformers",
                    extra={'requestId': transform_req.request_id})
        namespace = current_app.config['TRANSFORMER_NAMESPACE']
        transformer_manager.shutdown_transformer_job(transform_req.request_id, namespace)
