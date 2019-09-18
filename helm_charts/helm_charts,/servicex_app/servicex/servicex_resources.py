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

from flask import current_app
from flask import request
from flask_restful import Resource, reqparse

from servicex.models import TransformRequest, TransformationResult

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


def _generate_advertised_endpoint(endpoint):
    return "http://" + current_app.config['ADVERTISED_HOSTNAME'] + "/" + endpoint


class QueryTransformationRequest(Resource):
    def get(self, request_id=None):
        if request_id:
            return TransformRequest.to_json(
                TransformRequest.return_request(request_id)
            )
        else:
            return TransformRequest.return_all()


class AddFileToDataset(Resource):
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
            "service-endpoint": _generate_advertised_endpoint(
                "servicex/transformation/" + request_id
            )
        }

        try:
            self.rabbit_mq_adaptor.basic_publish(exchange='transformation_requests',
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
    @classmethod
    def make_api(cls, rabbitmq_adaptor):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        return cls

    def post(self, request_id):
        body = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)

        preflight_request = {
            'request-id': submitted_request.request_id,
            'columns': submitted_request.columns,
            'file-path': body['file_path'],
            "service-endpoint": _generate_advertised_endpoint(
                "servicex/transformation/" + request_id
            )
        }

        try:
            self.rabbit_mq_adaptor.basic_publish(exchange='',
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
        summary = request.get_json()
        rec = TransformRequest.return_request(request_id)
        rec.files = summary['files']
        rec.files_skipped = summary['files-skipped']
        rec.total_events = summary['total-events']
        rec.total_bytes = summary['total-bytes']
        rec.did_lookup_time = summary['elapsed-time']
        TransformRequest.update_request(rec)
        print("Complete "+request_id)


class TransformerFileComplete(Resource):
    @classmethod
    def make_api(cls, transformer_manager):
        cls.transformer_manager = transformer_manager
        return cls

    def put(self, request_id):
        info = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)
        rec = TransformationResult(
            did=submitted_request.did,
            request_id=request_id,
            file_path=info['file-path'],
            transform_status=info['status'],
            transform_time=info['total-time'],
            messages=info['num-messages']
        )
        rec.save_to_db()

        files_remaining = TransformRequest.files_remaining(request_id)
        if files_remaining and files_remaining <= 0:
            namepsace = current_app.config['TRANSFORMER_NAMESPACE']
            print("Job is all done... shutting down transformers")
            self.transformer_manager.shutdown_transformer_job(request_id, namepsace)
        print(info)
        return "Ok"
