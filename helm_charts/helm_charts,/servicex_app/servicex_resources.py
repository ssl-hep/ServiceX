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

import pika
from flask_restful import Resource, reqparse
import uuid
from models import TransformRequest
from run import app

rabbitmq = pika.BlockingConnection(
    pika.ConnectionParameters(
        app.config['RABBIT_MQ_URL']))

channel = rabbitmq.channel()
channel.queue_declare(queue='did_requests')
channel.queue_declare(queue='validation_requests')
channel.queue_declare(queue='transformation_requests')


parser = reqparse.RequestParser()
parser.add_argument('did', help='This field cannot be blank',
                    required=True)
parser.add_argument('columns', help='This field cannot be blank',
                    required=True)


class SubmitTransformationRequest(Resource):
    def post(self):
        request = parser.parse_args()
        request_id = uuid.uuid4()

        request_rec = TransformRequest(
            did=request['did'],
            columns=request['columns'],
            request_id=str(request_id)
        )

        did_request = {
            "request_id": request_rec.request_id,
            "did": request_rec.did,
            "columns": request_rec.columns,
            "status-endpoint": "http://host.docker.internal:5000/servicex/transformation/"+request_rec.request_id+"/status"
        }

        try:
            channel.basic_publish(exchange='',
                                  routing_key='did_requests',
                                  body=json.dumps(did_request))

            request_rec.save_to_db()
            return {
                "request_id": str(request_id)
            }

        except Exception as eek:
            print(eek)
            return {'message': 'Something went wrong'}, 500


status_parser = reqparse.RequestParser()
status_parser.add_argument('timestamp', help='This field cannot be blank',
                           required=True)
status_parser.add_argument('status', help='This field cannont be blank',
                           required=True)


class TransformationStatus(Resource):
    def post(self, request_id):
        status = status_parser.parse_args()
        status.request_id = request_id
        print(status)


class QueryTransformationRequest(Resource):
    def get(self, request_id=None):
        if request_id:
            return TransformRequest.return_request(request_id)
        else:
            return TransformRequest.return_all()
