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
import json
from servicex.models import TransformRequest
from flask import current_app

# TODO rename to something more descriptive


class LookupResultProcessor:
    def __init__(self, rabbitmq_adaptor, advertised_endpoint):
        self.rabbitmq_adaptor = rabbitmq_adaptor
        self.advertised_endpoint = advertised_endpoint

    def increment_files_in_request(self, submitted_request):
        TransformRequest.add_a_file(submitted_request.request_id)

    def add_files_to_processing_queue(self, request):
        for file_record in request.all_files:
            transform_request = {
                'request-id': request.request_id,
                'file-id': file_record.id,
                'columns': request.columns,
                'paths': file_record.paths,
                'tree-name': request.tree_name,
                "service-endpoint": self.advertised_endpoint +
                "servicex/internal/transformation/" + request.request_id,
                "chunk-size": "1000",
                "result-destination": request.result_destination,
                "result-format": request.result_format
            }
            self.rabbitmq_adaptor.basic_publish(exchange='transformation_requests',
                                                routing_key=request.request_id,
                                                body=json.dumps(transform_request))

        current_app.logger.info("Added all files to processing queue", extra={
            'requestId': request.request_id})
