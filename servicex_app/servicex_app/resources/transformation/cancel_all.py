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

from servicex_app.decorators import auth_required
from servicex_app.models import TransformRequest, db, TransformStatus
from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.transformer_manager import TransformerManager


class CancelAllTransforms(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager: TransformerManager):
        cls.transformer_manager = transformer_manager

    @auth_required
    def post(self):
        if not current_app.config.get("ENABLE_AUTH"):
            return {"message": "This is not available when auth is disabled"}, 400

        user = self.get_requesting_user()
        if user is None:
            return {"message": "No user found"}, 400

        transform_reqs = TransformRequest.active_user_transformations(user)

        canceled_ids = []
        now = datetime.now(tz=timezone.utc)

        for transform_req in transform_reqs:
            try:
                self.transformer_manager.cancel_transform(transform_req)
            except kubernetes.client.exceptions.ApiException:
                pass

            transform_req.status = TransformStatus.canceled
            transform_req.finish_time = now
            canceled_ids.append(transform_req.request_id)

        db.session.commit()
        return {"canceled": canceled_ids}, 200
