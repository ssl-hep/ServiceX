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
import sys
import traceback
from datetime import datetime
from datetime import timezone
import json
import uuid

from flask import current_app
from flask_restful import reqparse

from servicex.models import TransformRequest, DatasetFile
from servicex.resources.servicex_resource import ServiceXResource
from werkzeug.exceptions import BadRequest

parser = reqparse.RequestParser()
parser.add_argument('did', help='Dataset Identifier. Provide this or file-list',
                    required=False)

parser.add_argument('file-list',
                    type=list,
                    default=[],
                    location='json',
                    help='Static list of Root Files. Provide this orDataset Identifier. ',
                    required=False)

parser.add_argument('columns', help='This field cannot be blank',
                    required=False)
parser.add_argument('selection', help='This field or columns must be provided', required=False)
parser.add_argument('image', required=False)
parser.add_argument('chunk-size', required=False, type=int)
parser.add_argument('workers', required=False, type=int)
parser.add_argument('result-destination', required=True, choices=['kafka', 'object-store'])
parser.add_argument('result-format', required=False,
                    choices=['arrow', 'parquet', 'root-file'], default='arrow')
parser.add_argument('kafka', required=False, type=dict)

kafka_parser = reqparse.RequestParser()
kafka_parser.add_argument('broker', required=False, location=('kafka'))


def _workflow_name(transform_request):
    'Look at the keys and determine what sort of a workflow we want to run'
    has_columns = ('columns' in transform_request) and transform_request['columns']
    has_selection = ('selection' in transform_request) and transform_request['selection']
    if has_columns and not has_selection:
        return 'straight_transform'
    if not has_columns and has_selection:
        return 'selection_codegen'
    raise ValueError('Cannot determine workflow from argument - '
                     'selection or columns must be given, and not both')


class SubmitTransformationRequest(ServiceXResource):
    @classmethod
    def make_api(cls, rabbitmq_adaptor, object_store, elasticsearch_adapter,
                 code_gen_service, lookup_result_processor):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        cls.object_store = object_store
        cls.elasticsearch_adapter = elasticsearch_adapter
        cls.code_gen_service = code_gen_service
        cls.lookup_result_processor = lookup_result_processor
        return cls

    def post(self):
        try:
            transformation_request = parser.parse_args()

            request_id = str(uuid.uuid4())
            time = datetime.now(tz=timezone.utc)

            requested_did = transformation_request['did'] \
                if 'did' in transformation_request else None
            requested_file_list = transformation_request['file-list'] \
                if 'file-list' in transformation_request else None

            # requested_did xor requested_file_list
            if bool(requested_did) == bool(requested_file_list):
                raise BadRequest("Must provide did or file-list but not both")

            if self.object_store and \
                    transformation_request['result-destination'] == 'object-store':
                self.object_store.create_bucket(request_id)
                # WHat happens if object-store and object_store is None?

            if transformation_request['result-destination'] == 'kafka':
                broker = transformation_request['kafka']['broker']
            else:
                broker = None

            request_rec = TransformRequest(
                did=requested_did if requested_did else "File List Provided in Request",
                submit_time=time,
                columns=transformation_request['columns'],
                selection=transformation_request['selection'],
                request_id=str(request_id),
                image=transformation_request['image'],
                chunk_size=transformation_request['chunk-size'],
                result_destination=transformation_request['result-destination'],
                result_format=transformation_request['result-format'],
                kafka_broker=broker,
                workers=transformation_request['workers'],
                workflow_name=_workflow_name(transformation_request)
            )

            # If we are doing the xaod_cpp workflow, then the first thing to do is make
            # sure the requested selection is correct, and generate the C++ files
            if request_rec.workflow_name == 'selection_codegen':
                namespace = current_app.config['TRANSFORMER_NAMESPACE']
                request_rec.generated_code_cm = \
                    self.code_gen_service.generate_code_for_selection(request_rec, namespace)

            # Create queue for transformers to read from
            self.rabbitmq_adaptor.setup_queue(request_id)

            self.rabbitmq_adaptor.bind_queue_to_exchange(
                exchange="transformation_requests",
                queue=request_id)

            # Also setup an error queue for dead letters generated by transformer
            self.rabbitmq_adaptor.setup_queue(request_id+"_errors")

            self.rabbitmq_adaptor.bind_queue_to_exchange(
                exchange="transformation_failures",
                queue=request_id+"_errors")

            request_rec.save_to_db()

            if requested_did:
                did_request = {
                    "request_id": request_rec.request_id,
                    "did": request_rec.did,
                    "service-endpoint": self._generate_advertised_endpoint(
                        "servicex/transformation/" +
                        request_rec.request_id
                    )
                }

                self.rabbitmq_adaptor.basic_publish(exchange='',
                                                    routing_key='did_requests',
                                                    body=json.dumps(did_request))
            else:
                # Request a preflight check on the first file
                self.lookup_result_processor.publish_preflight_request(
                    request_rec,
                    requested_file_list[0])

                for file_path in requested_file_list:
                    file_record = DatasetFile(request_id=request_id,
                                              file_path=file_path,
                                              adler32="xxx",
                                              file_events=0,
                                              file_size=0)
                    self.lookup_result_processor.add_file_to_dataset(
                        request_rec,
                        file_record
                    )

                self.lookup_result_processor.report_fileset_complete(
                    request_rec,
                    num_files=len(requested_file_list)
                )

            if self.elasticsearch_adapter:
                self.elasticsearch_adapter.create_update_request(
                    request_id,
                    self._generate_transformation_record(request_rec, "locating DID"))

            return {
                "request_id": str(request_id)
            }
        except BadRequest as bad_request:
            return {'message': f'The json request was malformed: {str(bad_request)}'}, 400
        except ValueError as eek:
            return {'message': f'Failed to submit transform request: {str(eek)}'}, 400
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': 'Something went wrong'}, 500
