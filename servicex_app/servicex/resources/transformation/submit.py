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
from servicex.decorators import auth_required
from servicex.did_parser import DIDParser
from servicex.models import DatasetFile, Dataset, TransformRequest, db
from servicex.resources.internal.transform_start import TransformStart
from servicex.resources.servicex_resource import ServiceXResource
from werkzeug.exceptions import BadRequest


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
        cls.parser.add_argument('image')
        cls.parser.add_argument('codegen')
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

            image = args.get("image")
            did = args.get("did")
            file_list = args.get("file-list")
            user_codegen_name = args.get("codegen")

            code_gen_image_name = config['CODE_GEN_IMAGES'].get(user_codegen_name, None)

            if not code_gen_image_name:
                raise ValueError(f'Invalid Codegen Image Passed in Request: {user_codegen_name}')

            # did xor file_list
            if bool(did) == bool(file_list):
                raise BadRequest("Must provide did or file-list but not both")
            did_name = ''
            if did:
                parsed_did = DIDParser(
                    did, default_scheme=config['DID_FINDER_DEFAULT_SCHEME']
                )
                if parsed_did.scheme not in config['VALID_DID_SCHEMES']:
                    msg = f"DID scheme is not supported: {parsed_did.scheme}"
                    current_app.logger.warning(msg, extra={'requestId': request_id})
                    return {'message': msg}, 400
                did_name = parsed_did.full_did
            else:
                did_name = str(hash(str(file_list)))

            # Check if this dataset is already in the DB.
            dataset = Dataset.find_by_name(did_name)
            if not dataset:
                current_app.logger.info('dataset not in the db', extra={'requestId': request_id})
                dataset = Dataset(
                    name=did_name,
                    last_used=datetime.now(tz=timezone.utc),
                    last_updated=datetime.fromtimestamp(0),
                    lookup_status='',
                    did_finder=config['DID_FINDER_DEFAULT_SCHEME'] if did else 'user'
                )
                dataset.save_to_db()
                msg = f'new dataset created: {dataset.to_json()}'
                current_app.logger.info(msg, extra={'requestId': str(request_id)})
            else:
                current_app.logger.info('dataset found in the db', extra={'requestId': request_id})

            if dataset.lookup_status == '' and not did:
                current_app.logger.info("individual paths given", extra={
                    'requestId': str(request_id)})
                for paths in file_list:
                    file_record = DatasetFile(
                        dataset_id=dataset.id,
                        paths=paths,
                        adler32="xxx",
                        file_events=0,
                        file_size=0
                    )
                    file_record.save_to_db()
                dataset.n_files = len(file_list)
                dataset.lookup_status = 'complete'
                db.session.commit()

            if self.object_store and \
                    args['result-destination'] == \
                    TransformRequest.OBJECT_STORE_DEST:
                self.object_store.create_bucket(request_id)
                # TODO: need to check to make sure bucket was created
                # WHat happens if object-store and object_store is None?

            user = self.get_requesting_user()
            request_rec = TransformRequest(
                request_id=str(request_id),
                title=args.get("title"),
                did=did_name,
                did_id=dataset.id,
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
                code_gen_image=code_gen_image_name
            )

            # If we are doing the xaod_cpp workflow, then the first thing to do is make
            # sure the requested selection is correct, and generate the C++ files
            if request_rec.workflow_name == 'selection_codegen':
                namespace = config['TRANSFORMER_NAMESPACE']
                (request_rec.generated_code_cm,
                 codegen_transformer_image,
                 request_rec.transformer_language,
                 request_rec.transformer_command) = \
                    self.code_gen_service.generate_code_for_selection(request_rec, namespace,
                                                                      user_codegen_name)

                if not request_rec.image:
                    request_rec.image = codegen_transformer_image

            if config['TRANSFORMER_VALIDATE_DOCKER_IMAGE']:
                if not self.docker_repo_adapter.check_image_exists(request_rec.image):
                    msg = f"Requested transformer docker image doesn't exist: {request_rec.image}"
                    current_app.logger.error(msg, extra={'requestId': request_id})
                    return {'message': msg}, 400

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

            db.session.refresh(dataset)
            if dataset.lookup_status == '':
                current_app.logger.info("new dataset", extra={
                                        'requestId': str(request_id)})
                if did:
                    current_app.logger.info("adding dataset lookup to RMQ", extra={
                        'requestId': str(request_id)})
                    did_request = {
                        "request_id": request_id,
                        "dataset_id": dataset.id,
                        "did": parsed_did.did,
                        "endpoint": self._generate_advertised_endpoint(
                            "servicex/internal/transformation/"
                        )
                    }
                    self.rabbitmq_adaptor.basic_publish(exchange='',
                                                        routing_key=parsed_did.microservice_queue,
                                                        body=json.dumps(did_request))
                    dataset.lookup_status = 'looking'
                    db.session.commit()

            elif dataset.lookup_status == 'complete':
                current_app.logger.info("dataset already complete", extra={
                                        'requestId': str(request_id)})
                request_rec.files = dataset.n_files
                request_rec.status = 'Running'
                db.session.commit()

                self.lookup_result_processor.add_files_to_processing_queue(request_rec)

                # starts transformers

                if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
                    TransformStart.start_transformers(
                        self.transformer_manager,
                        current_app.config,
                        request_rec
                    )

            current_app.logger.info("Transformation request submitted!",
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
