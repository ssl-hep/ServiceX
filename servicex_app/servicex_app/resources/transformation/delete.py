# Copyright (c) 2024, IRIS-HEP
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
from servicex_app import ObjectStoreManager
from servicex_app.decorators import auth_required
from servicex_app.models import TransformRequest, TransformationResult, db
from servicex_app.resources.servicex_resource import ServiceXResource
from flask import current_app


class DeleteTransform(ServiceXResource):
    @classmethod
    def make_api(cls, object_store_manager: ObjectStoreManager):
        cls.object_store = object_store_manager

    @auth_required
    def delete(self, request_id: str):
        session = db.session
        with session.begin():

            transform_req = TransformRequest.lookup(request_id)
            if not transform_req:
                msg = f'Transformation request not found with id: {request_id}'
                current_app.logger.warning(msg, extra={'requestId': request_id})
                return {'message': msg}, 404

            if not transform_req.status.is_complete:
                msg = f"Transform request with id {request_id} is still in progress."
                current_app.logger.warning(msg, extra={'requestId': request_id})
                return {"message": msg}, 400

            user = self.get_requesting_user()
            if user and (not user.admin and user.id != transform_req.submitted_by):
                return {"message": "You are not authorized to delete this request"}, 403

            # Delete all the results for this transform
            session.query(TransformationResult).filter_by(
                request_id=transform_req.request_id).delete()

            # Delete the transformed files out of object store along with the bucket
            if self.object_store:
                self.object_store.delete_bucket_and_contents(transform_req.request_id)

            # Delete the transform request
            session.delete(transform_req)
        return {
            "message": f"Transform request with id {request_id} has been archived."
        }, 200
