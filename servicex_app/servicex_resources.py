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
from flask import request
from flask_restful import Resource, reqparse
import uuid
from models import TransformRequest
from run import app
from transformer_manager import launch_transformer_jobs

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
parser.add_argument('image', required=False)
parser.add_argument('chunk-size', required=False, type=int)
parser.add_argument('workers', required=False, type=int)
parser.add_argument('messaging-backend', required=False)
parser.add_argument('kafka-broker', required=False)


class SubmitTransformationRequest(Resource):
    def post(self):
        request = parser.parse_args()
        request_id = str(uuid.uuid4())

        request_rec = TransformRequest(
            did=request['did'],
            columns=request['columns'],
            request_id=str(request_id),
            image=request['image'],
            chunk_size=request['chunk-size'],
            messaging_backend=request['messaging-backend'],
            kafka_broker=request['kafka-broker'],
            workers=request['workers']
        )

        did_request = {
            "request_id": request_rec.request_id,
            "did": request_rec.did,
            "service-endpoint":
                "http://host.docker.internal:5000/servicex/transformation/" +
                request_rec.request_id
        }

        try:
            channel.queue_declare(request_id)
            channel.queue_bind(exchange="transformation_requests",
                               queue=request_id,
                               routing_key=request_id)

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
            return TransformRequest.to_json(
                TransformRequest.return_request(request_id)
            )
        else:
            return TransformRequest.return_all()


class AddFileToDataset(Resource):
    def put(self, request_id):
        add_file_request = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)

        transform_request = {
            'request-id': submitted_request.request_id,
            'columns': submitted_request.columns,
            'file_path': add_file_request['file_path'],
            "status-endpoint":
                "http://host.docker.internal:5000/servicex/transformation/" +
                submitted_request.request_id + "/status"
        }

        try:
            channel.basic_publish(exchange='transformation_requests',
                                  routing_key=request_id,
                                  body=json.dumps(transform_request))

            return {
                "request-id": str(request_id),
                "file-id": 42
            }

        except Exception as eek:
            print(eek)
            return {'message': 'Something went wrong'}, 500


class PreflightCheck(Resource):
    def post(self, request_id):
        body = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)

        preflight_request = {
            'request-id': submitted_request.request_id,
            'columns': submitted_request.columns,
            'file-path': body['file_path'],
            "service-endpoint":
                "http://host.docker.internal:5000/servicex/transformation/" +
                request_id
        }

        try:
            channel.basic_publish(exchange='',
                                  routing_key='validation_requests',
                                  body=json.dumps(preflight_request))

            return {
                "request-id": str(request_id),
                "file-id": 42
            }

        except Exception as eek:
            print(eek)
            return {'message': 'Something went wrong'}, 500


class FilesetComplete(Resource):
    def put(self, request_id):
        print("Complete "+request_id)


class TransformStart(Resource):
    def post(self, request_id):
        info = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)
        if app.config['TRANSFORMER_MANAGER_ENABLED']:
            launch_transformer_jobs(request_id, submitted_request.workers)
