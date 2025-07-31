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

from celery import Celery
from celery.utils.log import get_task_logger
from ..celery_task_router import route_task
import os

app = Celery("servicex.celery", broker=os.environ["RABBIT_MQ_URL"])
app.conf.task_routes = (route_task,)

ADVERTISED_ENDPOINT = f"http://{os.environ['INSTANCE_NAME']}-servicex-app:8000/"

logger = get_task_logger(__name__)


def celery_task_name(request_id):
    return f"transformer-{request_id}.transform_file"


@app.task
def add_files_to_processing_queue(request, files):
    from ..models import TransformStatus

    if TransformStatus.status_from_string(request["status"]).is_complete:
        logger.debug(
            "Rejecting file addition request, request is canceled",
            extra={"task_id": celery_task_name(request["request_id"])},
        )
        return
    for file_record in files:
        app.send_task(
            "transformer_sidecar.transform_file",
            kwargs={
                "request_id": request["request_id"],
                "file_id": file_record["id"],
                "paths": file_record["paths"].split(","),
                "service_endpoint": ADVERTISED_ENDPOINT
                + "servicex/internal/transformation/"
                + request["request_id"],
                "result_destination": request["result-destination"],
                "result_format": request["result-format"],
            },
        )

        logger.info(
            "Added file to processing queue",
            extra={
                "paths": file_record["paths"].split(","),
                "task_id": celery_task_name(request["request_id"]),
            },
        )

    logger.info(
        "Added files to processing queue",
        extra={"num_files": len(files), "requestId": request["request_id"]},
    )
