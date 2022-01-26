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

from servicex.models import TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource
from servicex.transformer_manager import TransformerManager


class TransformStart(ServiceXResource):
    @classmethod
    def start_transformers(cls, transformer_manager: TransformerManager,
                           config: dict,
                           request_rec: TransformRequest):
        rabbitmq_uri = config['TRANSFORMER_RABBIT_MQ_URL']
        namespace = config['TRANSFORMER_NAMESPACE']
        x509_secret = config['TRANSFORMER_X509_SECRET']
        generated_code_cm = request_rec.generated_code_cm

        transformer_manager.launch_transformer_jobs(
            image=request_rec.image, request_id=request_rec.request_id,
            workers=request_rec.workers,
            rabbitmq_uri=rabbitmq_uri,
            namespace=namespace,
            x509_secret=x509_secret,
            generated_code_cm=generated_code_cm,
            result_destination=request_rec.result_destination,
            result_format=request_rec.result_format)

    @classmethod
    def make_api(cls, transformer_manager: TransformerManager):
        """Initializes the transformer manage for this resource."""
        cls.transformer_manager = transformer_manager
        return cls

    def post(self, request_id):
        """
        Starts a transformation request, deploys transformers, and updates record.
        :param request_id: UUID of transformation request.
        """
        submitted_request = TransformRequest.lookup(request_id)

        if submitted_request.status == "Canceled":
            return {"message": "Transform request canceled by user."}, 409

        submitted_request.status = 'Running'
        submitted_request.save_to_db()
        db.session.commit()

        if current_app.config['TRANSFORMER_MANAGER_ENABLED']:
            TransformStart.start_transformers(
                self.transformer_manager,
                current_app.config,
                submitted_request)
