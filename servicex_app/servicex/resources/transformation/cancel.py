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
from datetime import datetime, timezone

import kubernetes
from flask import current_app

from servicex.decorators import auth_required
from servicex.models import TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource
from servicex.resources.internal.transform_start import TransformStart
from servicex.transformer_manager import TransformerManager


class CancelTransform(ServiceXResource):

    @auth_required
    def get(self, request_id: str):
        transform_req = TransformRequest.lookup(request_id)
        if not transform_req:
            msg = f'Transformation request not found with id: {request_id}'
            current_app.logger.warning(msg, extra={'requestId': request_id})
            return {'message': msg}, 404
        elif transform_req.complete:
            msg = f"Transform request with id {request_id} is not in progress."
            current_app.logger.warning(msg, extra={'requestId': request_id})
            return {"message": msg}, 400

        manager: TransformerManager = TransformStart.transformer_manager
        namespace = current_app.config['TRANSFORMER_NAMESPACE']

        if transform_req.status == "Running":
            try:
                manager.shutdown_transformer_job(request_id, namespace)
            except kubernetes.client.exceptions.ApiException as exc:
                if exc.status == 404:
                    pass
                else:
                    current_app.logger.error(f"Got Kubernetes api exception: {exc.reason}",
                                             extra={'requestId': request_id})
                    return {'message': exc.reason}, exc.status

        transform_req.status = "Canceled"
        transform_req.finish_time = datetime.now(tz=timezone.utc)
        transform_req.save_to_db()
        db.session.commit()

        return {"message": f"Canceled transformation request {request_id}"}, 200
