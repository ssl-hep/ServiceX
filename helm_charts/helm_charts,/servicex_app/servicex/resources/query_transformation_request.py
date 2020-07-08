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
from flask_jwt_extended import jwt_optional
from flask import current_app

from servicex.models import TransformRequest
from servicex.resources.servicex_resource import ServiceXResource


class QueryTransformationRequest(ServiceXResource):
    @jwt_optional
    def get(self, request_id=None):
        is_auth, auth_reject_message = self._validate_user()
        if not is_auth:
            return {'message': f'Authentication Failed: {str(auth_reject_message)}'}, 401

        if request_id:
            request_rec = TransformRequest.to_json(
                TransformRequest.return_request(request_id))

            if current_app.config['OBJECT_STORE_ENABLED'] and \
                    request_rec['result-destination'] == TransformRequest.OBJECT_STORE_DEST:
                request_rec['minio-endpoint'] = current_app.config['MINIO_PUBLIC_URL']
                request_rec['minio-access-key'] = current_app.config['MINIO_ACCESS_KEY']
                request_rec['minio-secret-key'] = current_app.config['MINIO_SECRET_KEY']
            return request_rec
        else:
            return TransformRequest.return_all()
