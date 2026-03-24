# Copyright (c) 2025, IRIS-HEP
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

from servicex_app.models import (
    Dataset,
    db,
    TransformRequest,
    TransformStatus,
    DatasetStatus,
)
from servicex_app.resources.servicex_resource import ServiceXResource

from datetime import datetime, timezone
import itertools


class FilesetError(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        summary = request.get_json()
        dataset = Dataset.find_by_id(int(dataset_id))

        if dataset is None:
            current_app.logger.info(
                "Dataset lookup error received for unknown dataset",
                extra={
                    "dataset_id": dataset_id,
                    "elapsed": summary["elapsed-time"],
                    "error_type": summary["error-type"],
                    "error": summary["message"],
                },
            )
            return "", 422

        current_app.logger.info(
            "Error in file lookup",
            extra={
                "dataset_id": dataset_id,
                "elapsed": summary["elapsed-time"],
                "error_type": summary["error-type"],
                "error": summary["message"],
            },
        )

        dataset.lookup_status = DatasetStatus(summary["error-type"])
        dataset.stale = True  # Repeat lookup if we try again
        db.session.commit()

        # shut down related running and pending transformations. Nothing good can
        # come of letting them continue to run
        namespace = current_app.config["TRANSFORMER_NAMESPACE"]
        for t_request in itertools.chain(
            TransformRequest.lookup_running_by_dataset_id(int(dataset_id)),
            TransformRequest.lookup_pending_on_dataset(int(dataset_id)),
        ):
            t_request.status = TransformStatus.bad_dataset
            t_request.finish_time = datetime.now(tz=timezone.utc)
            self.transformer_manager.shutdown_transformer_job(
                t_request.request_id, namespace
            )
            current_app.logger.info(
                "Shutting down transformer because of dataset lookup problem",
                extra={
                    "dataset_id": dataset_id,
                    "elapsed": summary["elapsed-time"],
                    "error_type": summary["error-type"],
                    "error": summary["message"],
                    "request_id": t_request.request_id,
                },
            )

        db.session.commit()
