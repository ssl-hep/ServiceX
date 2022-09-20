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
from flask import current_app
from flask_restful import reqparse

from servicex.decorators import auth_required
from servicex.models import TransformRequest
from servicex.resources.servicex_resource import ServiceXResource

parser = reqparse.RequestParser()


class TransformationRequest(ServiceXResource):
    @auth_required
    def get(self, request_id):
        # Validate that the user is an admin or submitted the request
        transform = TransformRequest.lookup(request_id)
        if not transform:
            msg = f'Transformation request not found with id: {request_id}'
            current_app.logger.error(msg, extra={'requestId': request_id})
            return {'message': msg}, 404
        transform_json = transform.to_json()
        if current_app.config['OBJECT_STORE_ENABLED'] and \
                transform_json['result-destination'] == TransformRequest.OBJECT_STORE_DEST:
            transform_json['minio-endpoint'] = current_app.config['MINIO_PUBLIC_URL']
            transform_json['minio-secured'] = current_app.config.get('MINIO_ENCRYPT_PUBLIC', True)
            transform_json['minio-access-key'] = current_app.config['MINIO_ACCESS_KEY']
            transform_json['minio-secret-key'] = current_app.config['MINIO_SECRET_KEY']
        return transform_json
