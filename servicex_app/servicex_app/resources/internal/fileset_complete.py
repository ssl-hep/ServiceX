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

from servicex_app.models import (
    Dataset,
    db,
    TransformRequest,
    TransformStatus,
    DatasetStatus,
)
from servicex_app.dataset_manager import DatasetManager
from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.transformer_manager import shutdown_finished_transformers

from datetime import datetime, timezone


class FilesetComplete(ServiceXResource):
    @classmethod
    def make_api(cls, lookup_result_processor, transformer_manager):
        cls.lookup_result_processor = lookup_result_processor
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, dataset_id):
        summary = request.get_json()
        dataset = Dataset.find_by_id(int(dataset_id))

        current_app.logger.info(
            "Completed fileset for datasetID",
            extra={"dataset_id": dataset_id, "elapsed": summary["elapsed-time"]},
        )
        dataset.n_files = summary["files"]
        dataset.events = summary["total-events"]
        dataset.size = summary["total-bytes"]
        dataset.lookup_status = DatasetStatus.complete
        db.session.commit()

        # Lock the transform requests waiting for this lookup. Until we commit, a
        # file-complete callback for one of them waits, so it cannot finish its last
        # file between our reading the counters and writing the status, and a
        # cancel that committed first removes the request from this list.
        waiting_requests = TransformRequest.lock_awaiting_dataset(int(dataset_id))
        finished_requests = []

        if summary["files"] > 0:
            dataset_manager = DatasetManager(dataset, current_app.logger, db)
            for transform_request in waiting_requests:
                if transform_request.status == TransformStatus.pending_lookup:
                    # This request came in while we were still looking up files,
                    # so send it the dataset now
                    dataset_manager.publish_files(
                        transform_request, self.lookup_result_processor
                    )
                transform_request.status = TransformStatus.running

            # A request whose files were all transformed before the lookup finished
            # gets no more file-complete callbacks, so it has to be completed here.
            # Re-read the counters after writing the status so the decision also
            # counts callbacks that committed before the write on a database that
            # does not lock rows (such as SQLite).
            db.session.flush()
            for transform_request in waiting_requests:
                db.session.refresh(transform_request)
                if transform_request.files_remaining == 0:
                    current_app.logger.info(
                        "All files already transformed. Shutting down transformers",
                        extra={"request_id": transform_request.request_id},
                    )
                    transform_request.status = TransformStatus.complete
                    transform_request.finish_time = datetime.now(tz=timezone.utc)
                    finished_requests.append(transform_request.request_id)

        else:
            current_app.logger.info(
                "No files found for datasetID. Shutting down transformers",
                extra={"dataset_id": dataset_id},
            )

            # There will never be any files, so neither the transform that prompted
            # this lookup nor any transform waiting for it will run
            for transform_request in waiting_requests:
                transform_request.status = TransformStatus.complete
                transform_request.finish_time = datetime.now(tz=timezone.utc)
                finished_requests.append(transform_request.request_id)

        db.session.commit()

        shutdown_finished_transformers(
            self.transformer_manager,
            finished_requests,
            current_app.config["TRANSFORMER_NAMESPACE"],
        )
