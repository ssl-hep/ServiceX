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
from datetime import datetime, timezone

from flask import current_app
from flask_restful import reqparse
from werkzeug.exceptions import BadRequest

from servicex.resources.internal.transform_start import TransformStart
from servicex.did_parser import DIDParser
from servicex.decorators import auth_required
from servicex.models import TransformRequest, DatasetFile, db
from servicex.resources.servicex_resource import ServiceXResource


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
                 code_gen_service, lookup_result_processor, docker_repo_adapter,
                 transformer_manager):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        cls.object_store = object_store
        cls.code_gen_service = code_gen_service
        cls.lookup_result_processor = lookup_result_processor
        cls.docker_repo_adapter = docker_repo_adapter
        cls.transformer_manager = transformer_manager

        cls.parser = reqparse.RequestParser()
        cls.parser.add_argument('title',
                                help='Optional title for this request (max 128 chars)')
        cls.parser.add_argument('did',
                                help='Dataset Identifier. Provide this or file-list')
        cls.parser.add_argument(
            'file-list',
            type=list,
            default=[],
            location='json',
            help='Static list of Root Files. Provide this or Dataset Identifier.'
        )
        cls.parser.add_argument('columns', help='This field cannot be blank')
        cls.parser.add_argument('selection', help='Query string')
        cls.parser.add_argument('image',
                                default=current_app.config['TRANSFORMER_DEFAULT_IMAGE'])
        cls.parser.add_argument('tree-name')
        cls.parser.add_argument('workers', type=int)
        cls.parser.add_argument('result-destination', required=True, choices=[
            TransformRequest.OBJECT_STORE_DEST,
            TransformRequest.VOLUME_DEST
        ])
        cls.parser.add_argument(
            'result-format', choices=['arrow', 'parquet', 'root-file'], default='arrow'
        )
        return cls

    @auth_required
    def post(self):
        request_id = str(uuid.uuid4())  # make sure we have a request id for all messages
        try:
            args = self.parser.parse_args()
            config = current_app.config

            image = args["image"]
            did = args.get("did")
            file_list = args.get("file-list")

            # did xor file_list
            if bool(did) == bool(file_list):
                raise BadRequest("Must provide did or file-list but not both")
            if did:
                parsed_did = DIDParser(
                    did, default_scheme=config['DID_FINDER_DEFAULT_SCHEME']
                )
                if parsed_did.scheme not in config['VALID_DID_SCHEMES']:
                    msg = f"DID scheme is not supported: {parsed_did.scheme}"
                    current_app.logger.warning(msg, extra={'requestId': request_id})
                    return {'message': msg}, 400

            if self.object_store and \
                    args['result-destination'] == \
                    TransformRequest.OBJECT_STORE_DEST:
                self.object_store.create_bucket(request_id)
                # TODO: need to check to make sure bucket was created
                # WHat happens if object-store and object_store is None?

            if config['TRANSFORMER_VALIDATE_DOCKER_IMAGE']:
                if not self.docker_repo_adapter.check_image_exists(image):
                    msg = f"Requested transformer docker image doesn't exist: {image}"
                    current_app.logger.error(msg, extra={'requestId': request_id})
                    return {'message': msg}, 400

            user = self.get_requesting_user()
            request_rec = TransformRequest(
                request_id=str(request_id),
                title=args.get("title"),
                did=parsed_did.full_did if did else "File List Provided in Request",
                submit_time=datetime.now(tz=timezone.utc),
                submitted_by=user.id if user is not None else None,
                columns=args['columns'],
                selection=args['selection'],
                tree_name=args['tree-name'],
                image=image,
                result_destination=args['result-destination'],
                result_format=args['result-format'],
                workers=args['workers'],
                workflow_name=_workflow_name(args),
                status='Submitted',
                app_version=self._get_app_version(),
                code_gen_image=config['CODE_GEN_IMAGE']
            )

            # If we are doing the xaod_cpp workflow, then the first thing to do is make
            # sure the requested selection is correct, and generate the C++ files
            if request_rec.workflow_name == 'selection_codegen':
                namespace = config['TRANSFORMER_NAMESPACE']
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

            except Exception:
                current_app.logger.exception("Unable to create transformer exchange",
                                             extra={'requestId': request_id})
                return {'message': "Error setting up transformer queues"}, 503

            request_rec.save_to_db()
            db.session.commit()

            if did:
                did_request = {
                    "request_id": request_rec.request_id,
                    "did": parsed_did.did,
                    "service-endpoint": self._generate_advertised_endpoint(
                        "servicex/internal/transformation/" +
                        request_rec.request_id
                    )
                }

                self.rabbitmq_adaptor.basic_publish(exchange='',
                                                    routing_key=parsed_did.microservice_queue,
                                                    body=json.dumps(did_request))
            else:
                for paths in file_list:
                    file_record = DatasetFile(request_id=request_id,
                                              paths=paths,
                                              adler32="xxx",
                                              file_events=0,
                                              file_size=0)
                    self.lookup_result_processor.add_file_to_dataset(
                        request_rec,
                        file_record
                    )

                self.lookup_result_processor.report_fileset_complete(
                    request_rec,
                    num_files=len(file_list)
                )

                db.session.commit()

                if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
                    TransformStart.start_transformers(
                        self.transformer_manager,
                        current_app.config,
                        request_rec
                    )

            current_app.logger.info("Transformation request submitted",
                                    extra={'requestId': request_id})
            return {
                "request_id": str(request_id)
            }
        except BadRequest as bad_request:
            msg = f'The json request was malformed: {str(bad_request)}'
            current_app.logger.error(msg, extra={'requestId': request_id})
            return {'message': msg}, 400
        except ValueError as eek:
            current_app.logger.exception("Failed to submit transform request",
                                         extra={'requestId': request_id})
            return {'message': f'Failed to submit transform request: {str(eek)}'}, 400
        except Exception:
            current_app.logger.exception("Got exception while submitting transformation request",
                                         extra={'requestId': request_id})
            return {'message': 'Something went wrong'}, 500
