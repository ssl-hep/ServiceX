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
from flask_restful import Resource, reqparse
import uuid
from servicex.models import TransformRequest, TransformationResult
from servicex.transformer_manager import launch_transformer_jobs, shutdown_transformer_job
from servicex.rabbit_adaptor import RabbitAdaptor
from flask import current_app, g


rabbit_mq_adaptor = RabbitAdaptor(current_app.config['RABBIT_MQ_URL'])
rabbit_mq_adaptor.connect()

# Insure the required queues and exchange exist in RabbitMQ broker
rabbit_mq_adaptor.setup_queue('did_requests')
rabbit_mq_adaptor.setup_queue('validation_requests')
rabbit_mq_adaptor.setup_exchange('transformation_requests')

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


def _files_remaining(request_id):
    submitted_request = TransformRequest.return_request(request_id)
    count = TransformationResult.count(request_id)
    if submitted_request.files and count:
        return submitted_request.files - count
    else:
        return None


class SubmitTransformationRequest(Resource):
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
            "service-endpoint": _generate_advertised_endpoint(
                "servicex/transformation/" +
                request_rec.request_id
            )
        }

        try:
            rabbit_mq_adaptor.setup_queue(request_id)

            rabbit_mq_adaptor.bind_queue_to_exchange(
                exchange="transformation_requests",
                queue=request_id)

            rabbit_mq_adaptor.basic_publish(exchange='',
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

    def get(self, request_id):
        count = TransformationResult.count(request_id)
        stats = TransformationResult.statistics(request_id)
        print(count, stats)
        print(_files_remaining(request_id))
        return str({
            "request-id": request_id,
            "files-processed": count,
            "files-remaining": _files_remaining(request_id),
            "stats": stats
        })


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
            'file-path': add_file_request['file_path'],
            "service-endpoint": _generate_advertised_endpoint(
                "servicex/transformation/" + request_id
            )
        }

        try:
            rabbit_mq_adaptor.basic_publish(exchange='transformation_requests',
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
            "service-endpoint": _generate_advertised_endpoint(
                "servicex/transformation/" + request_id
            )
        }

        try:
            rabbit_mq_adaptor.basic_publish(exchange='',
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


class TransformStart(Resource):
    def post(self, request_id):
        info = request.get_json()
        submitted_request = TransformRequest.return_request(request_id)
        if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
            rabbitmq_uri = current_app.config['TRANSFORMER_RABBIT_MQ_URL']
            namepsace = current_app.config['TRANSFORMER_NAMESPACE']
            print(rabbitmq_uri)
            launch_transformer_jobs(request_id,
                                    submitted_request.workers,
                                    submitted_request.chunk_size,
                                    rabbitmq_uri, namepsace)


class TransformerFileComplete(Resource):
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

        files_remaining = _files_remaining(request_id)
        if files_remaining and  files_remaining <= 0:
            namepsace = current_app.config['TRANSFORMER_NAMESPACE']
            print("Job is all done... shutting down transformers")
            shutdown_transformer_job(request_id, namepsace)
        print(info)
        return "Ok"
