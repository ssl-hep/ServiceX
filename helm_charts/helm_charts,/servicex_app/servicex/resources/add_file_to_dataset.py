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

from flask import request

from servicex.models import TransformRequest
from servicex.resources.servicex_resource import ServiceXResource


class AddFileToDataset(ServiceXResource):
    @classmethod
    def make_api(cls, rabbitmq_adaptor):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        return cls

    def put(self, request_id):
        add_file_request = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)

        transform_request = {
            'request-id': submitted_request.request_id,
            'columns': submitted_request.columns,
            'file-path': add_file_request['file_path'],
            "service-endpoint": self._generate_advertised_endpoint(
                "servicex/transformation/" + request_id
            ),
            "result-destination": submitted_request.result_destination
        }

        if submitted_request.result_destination == 'kafka':
            transform_request.update(
                {'kafka-broker': submitted_request.kafka_broker}
            )

        try:
            self.rabbitmq_adaptor.basic_publish(exchange='transformation_requests',
                                                routing_key=request_id,
                                                body=json.dumps(transform_request))

            return {
                "request-id": str(request_id),
                "file-id": 42
            }

        except Exception as eek:
            print(eek)
            return {'message': 'Something went wrong'}, 500
