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
import sys
import traceback
import uuid
from datetime import datetime, timezone

from flask import current_app
from flask_restful import reqparse
from werkzeug.exceptions import BadRequest

from servicex.did_parser import DIDParser
from servicex.decorators import auth_required
from servicex.models import TransformRequest, DatasetFile, db
from servicex.resources.servicex_resource import ServiceXResource

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
parser.add_argument('selection', help='Query string', required=False)
parser.add_argument('image', required=False)
parser.add_argument('tree-name', required=False)
parser.add_argument('chunk-size', required=False, type=int)
parser.add_argument('workers', required=False, type=int)
parser.add_argument('result-destination', required=True, choices=[
    TransformRequest.KAFKA_DEST,
    TransformRequest.OBJECT_STORE_DEST
])
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
    def make_api(cls, rabbitmq_adaptor, object_store,
                 code_gen_service, lookup_result_processor, docker_repo_adapter):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        cls.object_store = object_store
        cls.code_gen_service = code_gen_service
        cls.lookup_result_processor = lookup_result_processor
        cls.docker_repo_adapter = docker_repo_adapter
        return cls

    @auth_required
    def post(self):
        try:
            transformation_request = parser.parse_args()
            print("object store ", self.object_store)

            request_id = str(uuid.uuid4())
            time = datetime.now(tz=timezone.utc)

            transformer_image = transformation_request['image'] \
                if transformation_request['image'] \
                else current_app.config['TRANSFORMER_DEFAULT_IMAGE']

            requested_did = transformation_request['did'] \
                if 'did' in transformation_request else None
            requested_file_list = transformation_request['file-list'] \
                if 'file-list' in transformation_request else None

            # requested_did xor requested_file_list
            if bool(requested_did) == bool(requested_file_list):
                raise BadRequest("Must provide did or file-list but not both")

            if self.object_store and \
                    transformation_request['result-destination'] == \
                    TransformRequest.OBJECT_STORE_DEST:
                self.object_store.create_bucket(request_id)
                # WHat happens if object-store and object_store is None?

            if transformation_request['result-destination'] == TransformRequest.KAFKA_DEST:
                broker = transformation_request['kafka']['broker']
            else:
                broker = None

            if current_app.config['TRANSFORMER_VALIDATE_DOCKER_IMAGE']:
                tagged_image = transformer_image
                if not self.docker_repo_adapter.check_image_exists(tagged_image):
                    return {'message': f"The requested transformer docker image doesn't exist: {tagged_image}"}, 400  # noqa: E501

            request_rec = TransformRequest(
                did=requested_did if requested_did else "File List Provided in Request",
                submit_time=time,
                columns=transformation_request['columns'],
                selection=transformation_request['selection'],
                tree_name=transformation_request['tree-name'],
                request_id=str(request_id),
                image=transformer_image,
                chunk_size=transformation_request['chunk-size'],
                result_destination=transformation_request['result-destination'],
                result_format=transformation_request['result-format'],
                kafka_broker=broker,
                workers=transformation_request['workers'],
                workflow_name=_workflow_name(transformation_request),
                status='Submitted',
                app_version=self._get_app_version(),
                code_gen_image=current_app.config['CODE_GEN_IMAGE']
            )
            user = self.get_requesting_user()
            if user:
                request_rec.submitted_by = user.id

            # If we are doing the xaod_cpp workflow, then the first thing to do is make
            # sure the requested selection is correct, and generate the C++ files
            if request_rec.workflow_name == 'selection_codegen':
                namespace = current_app.config['TRANSFORMER_NAMESPACE']
                request_rec.generated_code_cm = \
                    self.code_gen_service.generate_code_for_selection(request_rec, namespace)

            # Insure the required queues and exchange exist in RabbitMQ broker
            try:
                self.rabbitmq_adaptor.setup_exchange('transformation_requests')
                self.rabbitmq_adaptor.setup_exchange('transformation_failures')

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

            except Exception as eek:
                print("Unable to create transformer exchange", eek)
                return {'message': "Error setting up transformer queues"}, 503

            request_rec.save_to_db()
            db.session.commit()

            if requested_did:
                did_request = {
                    "request_id": request_rec.request_id,
                    "did": request_rec.did,
                    "service-endpoint": self._generate_advertised_endpoint(
                        "servicex/internal/transformation/" +
                        request_rec.request_id
                    )
                }

                parsed_did = DIDParser(requested_did,
                                       default_scheme=current_app.config[
                                           'DID_FINDER_DEFAULT_SCHEME'])

                if parsed_did.scheme not in current_app.config['VALID_DID_SCHEMES']:
                    return {'message': f"The requested DID scheme is not supported: {parsed_did.scheme}"}, 400  # noqa: E501

                self.rabbitmq_adaptor.basic_publish(exchange='',
                                                    routing_key=parsed_did.microservice_queue,
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

                db.session.commit()

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
