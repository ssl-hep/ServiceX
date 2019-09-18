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
import uuid

from flask_restful import reqparse

from servicex.models import TransformRequest
from servicex.resources.servicex_resource import ServiceXResource

parser = reqparse.RequestParser()
parser.add_argument('did', help='This field cannot be blank',
                    required=True)
parser.add_argument('columns', help='This field cannot be blank',
                    required=True)
parser.add_argument('image', required=False)
parser.add_argument('chunk-size', required=False, type=int)
parser.add_argument('workers', required=False, type=int)
parser.add_argument('messaging-backend', required=False)
parser.add_argument('kafka-broker', required=False)


class SubmitTransformationRequest(ServiceXResource):
    @classmethod
    def make_api(cls, rabbitmq_adaptor):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        return cls

    def post(self):
        transformation_request = parser.parse_args()
        request_id = str(uuid.uuid4())

        request_rec = TransformRequest(
            did=transformation_request['did'],
            columns=transformation_request['columns'],
            request_id=str(request_id),
            image=transformation_request['image'],
            chunk_size=transformation_request['chunk-size'],
            messaging_backend=transformation_request['messaging-backend'],
            kafka_broker=transformation_request['kafka-broker'],
            workers=transformation_request['workers']
        )

        did_request = {
            "request_id": request_rec.request_id,
            "did": request_rec.did,
            "service-endpoint": self._generate_advertised_endpoint(
                "servicex/transformation/" +
                request_rec.request_id
            )
        }

        try:
            self.rabbitmq_adaptor.setup_queue(request_id)

            self.rabbitmq_adaptor.bind_queue_to_exchange(
                exchange="transformation_requests",
                queue=request_id)

            self.rabbitmq_adaptor.basic_publish(exchange='',
                                                routing_key='did_requests',
                                                body=json.dumps(did_request))

            request_rec.save_to_db()
            return {
                "request_id": str(request_id)
            }

        except Exception as eek:
            print(eek)
            return {'message': 'Something went wrong'}, 500
