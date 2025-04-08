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
import time
from datetime import datetime, timezone
from functools import wraps
from logging import Logger

from flask import current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tenacity import after_log, before_sleep_log, retry, retry_if_not_exception_type, \
    stop_after_attempt, wait_exponential_jitter

from servicex_app import TransformerManager
from servicex_app.models import TransformRequest, TransformStatus, TransformationResult, \
    db
from servicex_app.resources.servicex_resource import ServiceXResource


def file_complete_ops_retry(func):
    """
    A decorator that applies a standard retry mechanism for file complete operations.

    This decorator wraps the target function with a retry mechanism using the tenacity library.
    It attempts to execute the function up to 3 times, with exponential backoff and jitter
    between retries. The decorator also logs retry attempts and results.

    Note:
    This decorator is designed to work both within and outside of a Flask application context.
    It dynamically evaluates the logger at runtime to support usage in various environments,
    including unit tests.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        try:
            from flask import current_app
            logger = current_app.logger
        except RuntimeError:
            logger = logging.getLogger(__name__)

        return retry(
            retry=retry_if_not_exception_type(IntegrityError),
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=0.1, max=30),
            before_sleep=before_sleep_log(logger, logging.INFO),
            after=after_log(logger, logging.INFO)
        )(func)(*args, **kwargs)

    return wrapper


class TransformerFileComplete(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager, logger=None):
        cls.transformer_manager = transformer_manager
        cls.logger = logger or logging.getLogger(__name__)
        return cls

    def put(self, request_id):
        start_time = time.time()
        info = request.get_json()
        logger = current_app.logger
        log_extra = {
                    'requestId': request_id,
                    'file-id': info['file-id']
        }

        logger.info("FileComplete", extra={**log_extra, 'metric': info})
        try:
            session = db.session

            try:
                # Add the transformation result to the database and verify that
                # we've not processed this file already
                self.save_transform_result(request_id, info, session)
            except IntegrityError:
                logger.warning("Ignoring duplicate result report",
                               extra=log_extra)
                return "Ignoring duplicate result report", 200

            # Lookup the transformation request and increment either the successful or failed file count
            transform_req = self.record_file_complete(session,
                                                      current_app.logger,
                                                      request_id,
                                                      info, log_extra)

            if transform_req is None:
                logger.error("Request not found", extra=log_extra)
                return "Request not found", 404

            # Now we can see if we are done with the transformation and
            # can shut down the transformers. Files remaining is None if
            # we are still waiting for final results from the DID finder
            with session.begin():
                files_remaining = transform_req.files_remaining
                if files_remaining is not None and files_remaining == 0:
                    self.transform_complete(session, current_app.logger, transform_req, self.transformer_manager)

            current_app.logger.info("FileComplete. Request state.", extra={
                **log_extra,
                'files_remaining': transform_req.files_remaining,
                'files_completed': transform_req.files_completed,
                'files_failed': transform_req.files_failed,
                'report_processed_time': (time.time() - start_time)
            })
            return "Ok", 200
        except Exception as e:
            logger.exception("Error processing file complete",
                             extra=log_extra, exc_info=e)
            return "Error processing file complete", 500

    @staticmethod
    @file_complete_ops_retry
    def record_file_complete(session: Session, logger: Logger, request_id: str,
                             info: dict[str, str], log_extra: dict[str, str]) -> TransformRequest | None:

        with session.begin():
            # Lock the row for update
            transform_req = session.query(TransformRequest).filter_by(
                request_id=request_id).with_for_update().one_or_none()

            if transform_req is None:
                msg = f"Request not found with id: '{request_id}'"
                logger.error(msg, extra=log_extra)
                return None

            if info['status'] == 'success':
                transform_req.files_completed += 1
                transform_req.total_bytes += info['total-bytes']
                transform_req.total_events += info['total-events']
            else:
                transform_req.files_failed += 1

        return transform_req

    @staticmethod
    @file_complete_ops_retry
    def save_transform_result(request_id: str, info: dict[str, str], session: Session):
        with session.begin():
            rec = TransformationResult(
                file_id=info['file-id'],
                request_id=request_id,
                file_path=info['file-path'],
                transform_status=info['status'],
                transform_time=info['total-time'],
                total_bytes=info['total-bytes'],
                total_events=info['total-events'],
                avg_rate=info['avg-rate']
            )
            session.add(rec)

    @staticmethod
    @file_complete_ops_retry
    def transform_complete(session: Session, logger: Logger, transform_req: TransformRequest,
                           transformer_manager: TransformerManager):
        transform_req.status = TransformStatus.complete
        transform_req.finish_time = datetime.now(tz=timezone.utc)
        session.add(transform_req)

        logger.info("Request completed. Shutting down transformers",
                    extra={'requestId': transform_req.request_id})
        namespace = current_app.config['TRANSFORMER_NAMESPACE']
        transformer_manager.shutdown_transformer_job(transform_req.request_id, namespace)
