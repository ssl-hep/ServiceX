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
    def make_api(cls, transformer_manager: TransformerManager):
        """Initializes the transformer manage for this resource."""
        cls.transformer_manager = transformer_manager
        return cls

    def post(self, request_id):
        """
        Starts a transformation request, deploys transformers, and updates record.
        :param request_id: UUID of transformation request.
        """
        from servicex.kafka_topic_manager import KafkaTopicManager
        submitted_request = TransformRequest.return_request(request_id)

        if submitted_request.status == "Stopped":
            return {"message": "Transform request stopped by user."}, 409

        submitted_request.status = 'Running'
        submitted_request.save_to_db()
        db.session.commit()

        if current_app.config['TRANSFORMER_MANAGER_ENABLED']:

            if submitted_request.result_destination == 'kafka':
                # Setup the kafka topic with the correct number of partitions and max
                # message size
                max_message_size = 1920000
                kafka = KafkaTopicManager(submitted_request.kafka_broker)
                kafka.create_topic(request_id,
                                   max_message_size=max_message_size,
                                   num_partitions=100)

            rabbitmq_uri = current_app.config['TRANSFORMER_RABBIT_MQ_URL']
            namespace = current_app.config['TRANSFORMER_NAMESPACE']
            x509_secret = current_app.config['TRANSFORMER_X509_SECRET']
            generated_code_cm = submitted_request.generated_code_cm

            self.transformer_manager.launch_transformer_jobs(
                image=submitted_request.image, request_id=request_id,
                workers=submitted_request.workers,
                chunk_size=submitted_request.chunk_size, rabbitmq_uri=rabbitmq_uri,
                namespace=namespace,
                x509_secret=x509_secret,
                generated_code_cm=generated_code_cm,
                result_destination=submitted_request.result_destination,
                result_format=submitted_request.result_format,
                kafka_broker=submitted_request.kafka_broker)
