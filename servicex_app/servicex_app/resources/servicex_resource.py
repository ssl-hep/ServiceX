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
from typing import Any, Optional, Tuple

from importlib.metadata import version, PackageNotFoundError
from flask import current_app, session
from flask_jwt_extended import get_jwt_identity
from flask_restful import Resource
from servicex_app.models import UserModel, TransformRequest, TransformStatus

from servicex_app.transformer_manager import TransformerManager

from servicex_app.decorators import jwt_required_if_auth_enabled


class ServiceXResource(Resource):
    def __init__(self):
        """
        Initialize object
        """
        super().__init__()

    @classmethod
    def _generate_advertised_endpoint(cls, endpoint):
        return "http://" + current_app.config["ADVERTISED_HOSTNAME"] + "/" + endpoint

    @staticmethod
    @jwt_required_if_auth_enabled(optional=True)
    def get_requesting_user() -> Optional[UserModel]:
        """
        :return: User who submitted request for resource.
        If auth is enabled, this cannot be None for JWT-protected resources
        which are decorated with @auth_required or @admin_required.
        """
        user = None
        if current_app.config.get("ENABLE_AUTH"):
            if session.get("is_authenticated"):
                user = UserModel.find_by_id(session.get("user_id"))
            else:
                user = UserModel.find_by_email(get_jwt_identity())
        return user

    def _get_owned_request(self, request_id) -> Tuple[Optional[TransformRequest], Any]:
        """
        Look up a transform request and confirm that the requesting user is
        allowed to act on it.
        :return: A (transform request, error response) pair. The error response
        is None if the lookup succeeded and the user is an admin or the
        submitter, and is a 404 or 403 response otherwise.
        """
        transform_req = TransformRequest.lookup(request_id)
        if not transform_req:
            msg = f"Transformation request not found with id: {request_id}"
            current_app.logger.warning(msg, extra={"request_id": request_id})
            return None, ({"message": msg}, 404)

        if current_app.config.get("ENABLE_AUTH"):
            user = self.get_requesting_user()
            if not user or (not user.admin and user.id != transform_req.submitted_by):
                msg = "You are not authorized to access this request"
                current_app.logger.warning(msg, extra={"request_id": request_id})
                return None, ({"message": msg}, 403)

        return transform_req, None

    @classmethod
    def _get_app_version(cls):
        """
        Examine installed packages to get the version number for the ServiceX App
        :return: The version number, or the string "develop" if servicex_app not installed
        """
        try:
            return version("servicex_app")
        except PackageNotFoundError:
            return "develop"

    @classmethod
    def start_transformers(
        cls,
        transformer_manager: TransformerManager,
        config: dict,
        request_rec: TransformRequest,
    ):
        """
        Start the transformers for a given request
        """
        rabbitmq_uri = config["TRANSFORMER_RABBIT_MQ_URL"]
        namespace = config["TRANSFORMER_NAMESPACE"]
        x509_secret = config["TRANSFORMER_X509_SECRET"]
        generated_code_cm = request_rec.generated_code_cm

        request_rec.workers = min(max(1, request_rec.files), request_rec.workers)

        current_app.logger.info(
            f"Launching {request_rec.workers} transformers.",
            extra={"request_id": request_rec.request_id},
        )

        transformer_manager.launch_transformer_jobs(
            image=request_rec.image,
            request_id=request_rec.request_id,
            workers=request_rec.workers,
            max_workers=(
                max(1, request_rec.files)
                if request_rec.status == TransformStatus.running
                else config["TRANSFORMER_MAX_REPLICAS"]
            ),
            rabbitmq_uri=rabbitmq_uri,
            namespace=namespace,
            x509_secret=x509_secret,
            generated_code_cm=generated_code_cm,
            result_destination=request_rec.result_destination,
            result_format=request_rec.result_format,
            transformer_language=request_rec.transformer_language,
            transformer_command=request_rec.transformer_command,
        )
