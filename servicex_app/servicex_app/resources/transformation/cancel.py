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
from typing import Optional

import kubernetes
from flask import current_app

from servicex_app import orchestrator_mode
from servicex_app.decorators import auth_required
from servicex_app.models import TransformRequest, db, TransformStatus
from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.temporal_adaptor import TemporalAdaptor
from servicex_app.transformer_manager import TransformerManager


class CancelTransform(ServiceXResource):
    @classmethod
    def make_api(
        cls,
        transformer_manager: TransformerManager,
        temporal_adaptor: Optional[TemporalAdaptor] = None,
    ):
        cls.transformer_manager = transformer_manager
        cls.temporal_adaptor = temporal_adaptor

    @auth_required
    def get(self, request_id: str):
        """
        This is legacy functionality to support old clients
        """
        return self._cancel_transform(request_id)

    @auth_required
    def post(self, request_id: str):
        """
        This is supported via the cancel_transform_post_method capability
        """
        return self._cancel_transform(request_id)

    def _cancel_transform(self, request_id: str):
        transform_req = TransformRequest.lookup(request_id)
        if not transform_req:
            msg = f"Transformation request not found with id: {request_id}"
            current_app.logger.warning(msg, extra={"request_id": request_id})
            return {"message": msg}, 404
        elif transform_req.status.is_complete:
            msg = f"Transform request with id {request_id} is not in progress."
            current_app.logger.warning(msg, extra={"request_id": request_id})
            return {"message": msg}, 400

        if orchestrator_mode.use_temporal(current_app.config):
            try:
                # The workflow stops its pool and pilots and finalizes the row; its
                # finalize leaves the canceled status written below alone.
                if not self.temporal_adaptor.cancel_transform_request(request_id):
                    current_app.logger.info(
                        "No open workflow to cancel", extra={"request_id": request_id}
                    )
            except Exception as exc:
                current_app.logger.exception(
                    "Could not cancel the request's workflow",
                    extra={"request_id": request_id},
                )
                return {"message": f"Could not cancel the transform ({exc})"}, 503
        else:
            try:
                self.transformer_manager.cancel_transform(transform_req)
            except kubernetes.client.exceptions.ApiException as exc:
                return {"message": exc.reason}, exc.status

        transform_req.status = TransformStatus.canceled
        transform_req.finish_time = datetime.now(tz=timezone.utc)
        transform_req.save_to_db()
        db.session.commit()

        return {"message": f"Canceled transformation request {request_id}"}, 200
