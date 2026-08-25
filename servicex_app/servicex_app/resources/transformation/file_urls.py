# Copyright (c) 2026, IRIS-HEP
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
import datetime

from flask import current_app
from flask_restful import reqparse

from servicex_app.decorators import auth_required
from servicex_app.models import TransformRequest
from servicex_app.resources.servicex_resource import ServiceXResource

import boto3


class FileURLGenerator(ServiceXResource):
    def __init__(self):
        super().__init__()
        # Add branches for different backends when relevant
        # set up S3 client
        endpoint_url = (
            "https://"
            if current_app.config.get("MINIO_ENCRYPT_PUBLIC", True)
            else "http://"
        ) + current_app.config["MINIO_PUBLIC_URL"]
        self.s3client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=current_app.config["MINIO_ACCESS_KEY"],
            aws_secret_access_key=current_app.config["MINIO_SECRET_KEY"],
            use_ssl=current_app.config.get("MINIO_ENCRYPT_PUBLIC", True),
        )

    @auth_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("request_id", type=str, required=True, location="json")
        parser.add_argument("file_list", type=list, required=True, location="json")
        parser.add_argument(
            "scheme",
            type=str,
            choices=["http", "xrootd"],
            required=False,
            location="json",
        )

        args = parser.parse_args()
        request_id = args["request_id"]
        # Validate that the user is an admin or submitted the request (not yet implemented)
        transform = TransformRequest.lookup(request_id)
        if not transform:
            msg = f"Transformation request not found with id: {request_id}"
            current_app.logger.error(msg, extra={"request_id": request_id})
            return {"message": msg}, 404

        expirydelta = 365 * 24 * 60 * 60
        expiry = int(datetime.datetime.now().timestamp() + expirydelta)

        # Add branches for other backends when relevant
        if transform.result_destination != TransformRequest.OBJECT_STORE_DEST:
            msg = (
                f"Transformation request {request_id} does not use object-store "
                f"storage (result_destination={transform.result_destination}); "
                "cannot generate presigned URLs."
            )
            current_app.logger.error(msg, extra={"request_id": request_id})
            return {"message": msg}, 409

        if not transform.output_path:
            msg = (
                f"Transformation request {request_id} has no output_path "
                "recorded; cannot generate file URLs."
            )
            current_app.logger.error(msg, extra={"request_id": request_id})
            return {"message": msg}, 409

        rv = {
            f: (
                self.s3client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": transform.output_path, "Key": f},
                    ExpiresIn=expirydelta,
                ),
                {},
                expiry,
            )
            for f in args["file_list"]
        }

        return {"uris": rv}
