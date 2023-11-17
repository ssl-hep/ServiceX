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
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from flask import current_app
from flask_restful import reqparse
from servicex.dataset_manager import DatasetManager
from servicex.decorators import auth_required
from servicex.did_parser import DIDParser
from servicex.models import TransformRequest, db, TransformStatus
from servicex.resources.servicex_resource import ServiceXResource
from werkzeug.exceptions import BadRequest


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

    def _initialize_dataset_manager(self, did: Optional[str],
                                    file_list: Optional[List[str]],
                                    request_id: str,
                                    config: dict) -> DatasetManager:

        # did xor file_list
        if bool(did) == bool(file_list):
            raise BadRequest("Must provide did or file-list but not both")

        if did:
            parsed_did = DIDParser(
                did, default_scheme=config['DID_FINDER_DEFAULT_SCHEME']
            )
            if parsed_did.scheme not in config['VALID_DID_SCHEMES']:
                msg = f"DID scheme is not supported: {parsed_did.scheme}"
                raise BadRequest(msg)

            return DatasetManager.from_did(parsed_did.full_did,
                                           logger=current_app.logger,
                                           extras={
                                               'request_id': request_id
                                           }, db=db)
        else:  # no dataset, only a list of files given
            return DatasetManager.from_file_list(file_list,
                                                 logger=current_app.logger,
                                                 extras={
                                                     'request_id': request_id
                                                 }, db=db)

    def _setup_rabbit_queues(self, request_id: str):
        # Insure the required queues and exchange exist in RabbitMQ broker
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

    @auth_required
    def post(self):
        request_id = str(uuid.uuid4())  # make sure we have a request id for all messages
        try:

            try:
                args = self.parser.parse_args()
            except BadRequest as bad_request:
                msg = f'The json request was malformed: {str(bad_request)}'
                current_app.logger.error(msg, extra={'requestId': request_id})
                return {'message': msg}, 400

            config = current_app.config
            user = self.get_requesting_user()

            image = args.get("image")
            did = args.get("did")
            file_list = args.get("file-list")
            user_codegen_name = args.get("codegen")

            code_gen_image_name = config['CODE_GEN_IMAGES'].get(user_codegen_name, None)
            namespace = config['TRANSFORMER_NAMESPACE']

            if not code_gen_image_name:
                msg = f'Invalid Codegen Image Passed in Request: {user_codegen_name}'
                current_app.logger.error(msg, extra={'requestId': request_id})
                return {'message': msg}, 500

            try:
                dataset_manager = self._initialize_dataset_manager(did, file_list, request_id, config)
            except BadRequest as bad_request:
                current_app.logger.error(str(bad_request), extra={'requestId': request_id})
                return {'message': str(bad_request)}, 400

            # If the user has requested an object store destination, now is the time
            # to creat a bucket named after the request id
            if self.object_store and \
                    args['result-destination'] == \
                    TransformRequest.OBJECT_STORE_DEST:
                self.object_store.create_bucket(request_id)
                # TODO: need to check to make sure bucket was created
                # WHat happens if object-store and object_store is None?

            request_rec = TransformRequest(
                request_id=str(request_id),
                title=args.get("title"),
                did=dataset_manager.name,
                did_id=dataset_manager.id,
                submit_time=datetime.now(tz=timezone.utc),
                submitted_by=user.id if user is not None else None,
                columns=args['columns'],
                selection=args['selection'],
                tree_name=args['tree-name'],
                image=image,
                result_destination=args['result-destination'],
                result_format=args['result-format'],
                workers=args['workers'],
                status=TransformStatus.submitted,
                app_version=self._get_app_version(),
                code_gen_image=code_gen_image_name,
                files=0
            )

            # The first thing to do is make sure the requested selection is correct, and can generate
            # the requested code
            (request_rec.generated_code_cm,
             codegen_transformer_image,
             request_rec.transformer_language,
             request_rec.transformer_command) = \
                self.code_gen_service.generate_code_for_selection(request_rec, namespace,
                                                                  user_codegen_name)

            # If the user didn't specify an image, use the one from the codegen
            if not request_rec.image:
                request_rec.image = codegen_transformer_image

            # Check to make sure the transformer docker image actually exists (if enabled)
            if config['TRANSFORMER_VALIDATE_DOCKER_IMAGE']:
                if not self.docker_repo_adapter.check_image_exists(request_rec.image):
                    msg = f"Requested transformer docker image doesn't exist: {request_rec.image}"
                    current_app.logger.error(msg, extra={'requestId': request_id})
                    return {'message': msg}, 500

            # Insure the required queues and exchange exist in RabbitMQ broker
            try:
                self._setup_rabbit_queues(request_id)
            except Exception:
                current_app.logger.exception("Unable to create transformer exchange",
                                             extra={'requestId': request_id})
                return {'message': "Error setting up transformer queues"}, 503

            request_rec.save_to_db()
            dataset_manager.refresh()

            # If this request has a fresh DID then submit the lookup request to the DID Finder
            if dataset_manager.is_lookup_required:
                dataset_manager.submit_lookup_request(
                    self._generate_advertised_endpoint("servicex/internal/transformation/"),
                    self.rabbitmq_adaptor)
                request_rec.status = TransformStatus.lookup
            elif dataset_manager.is_complete:
                current_app.logger.info("dataset already complete", extra={
                                        'requestId': str(request_id)})
                dataset_manager.publish_files(request_rec, self.lookup_result_processor)
                request_rec.status = TransformStatus.running

            db.session.commit()

            # start transformers independently of the state of dataset.
            if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
                self.transformer_manager.start_transformers(
                    current_app.config,
                    request_rec
                )

            current_app.logger.info("Transformation request submitted!",
                                    extra={'requestId': request_id})
            return {
                "request_id": str(request_id)
            }
        except Exception as eek:
            current_app.logger.exception("Got exception while submitting transformation request",
                                         extra={'requestId': request_id})
            return {'message': f'Something went wrong ({str(eek)})'}, 500
