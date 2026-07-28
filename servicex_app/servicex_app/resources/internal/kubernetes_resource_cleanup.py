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
from flask import request, current_app
from datetime import datetime, timedelta, timezone


from servicex_app.resources.servicex_resource import ServiceXResource

from servicex_app.transformer_manager import TransformerManager


class CleanupKubernetesResources(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager: TransformerManager):
        cls.transformer_manager = transformer_manager
        return cls

    def post(self):
        # We first consider transformer jobs and reap those that are too old.
        # We then look at remaining configmaps, and if those are too old
        # delete the corresponding transform ID and hope that cleans up
        # everything, including lingering RabbitMQ queues.
        maxage = float(request.get_json().get("maxAge", 24))

        namespace = current_app.config["TRANSFORMER_NAMESPACE"]

        deleted: set[str] = set()  # list of request IDs we have tried to delete
        jobs = self.transformer_manager.get_all_transformer_jobs()
        configmaps = self.transformer_manager.get_all_transformer_configmaps()
        now = datetime.now(tz=timezone.utc)
        delta = timedelta(hours=maxage)
        logging_message = ["Kubernetes reaper report"]
        try:
            for job in jobs:
                age = now - job.metadata.creation_timestamp
                if age > delta:
                    id = job.metadata.name.replace("transformer-", "")
                    logging_message.append(f"Shutting down {id}, age {age}")
                    self.transformer_manager.shutdown_transformer_job(
                        id, namespace, True
                    )
                    deleted.add(id)
            for map in configmaps:
                age = now - map.metadata.creation_timestamp
                if age > delta:
                    id = map.metadata.name.replace("-generated-source", "")
                    if id not in deleted:
                        logging_message.append(f"Shutting down {id}, age {age}")
                        self.transformer_manager.shutdown_transformer_job(
                            id, namespace, True
                        )
                        deleted.add(id)
        except Exception as e:
            logging_message.append(str(e))
            current_app.logger.warning("\n".join(logging_message))
        else:
            current_app.logger.info("\n".join(logging_message))
