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
import kubernetes
from kubernetes import client
from flask import current_app


class TransformerManager:

    def __init__(self, manager_mode):
        if manager_mode == 'internal-kubernetes':
            kubernetes.config.load_incluster_config()
        elif manager_mode == 'external-kubernetes':
            kubernetes.config.load_kube_config()
        else:
            raise ValueError('Manager mode '+manager_mode+' not valid')

    def create_job_object(self, request_id, image, chunk_size, rabbitmq_uri, workers):
        if "TRANSFORMER_LOCAL_PATH" in current_app.config:
            path = current_app.config['TRANSFORMER_LOCAL_PATH']
            volumes = [client.V1Volume(
                name='rootfiles',
                host_path=client.V1HostPathVolumeSource(path=path))]
            volume_mounts = [client.V1VolumeMount(mount_path="/data", name='rootfiles')]
        else:
            volumes = []
            volume_mounts = []

        # Configure Pod template container
        container = client.V1Container(
            name="transformer-" + request_id,
            image=image,
            image_pull_policy='Always',
            volume_mounts=volume_mounts,
            command=["bash", "-c"],
            env=[client.V1EnvVar(name="BASH_ENV", value="/home/atlas/.bashrc")],
            args=["python xaod_branches.py " +
                  " --request-id " + request_id +
                  " --rabbit-uri " + rabbitmq_uri +
                  " --chunks " + str(chunk_size) +
                  " --kafka"])
        # Create and Configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": "transformer-" + request_id}),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                volumes=volumes))
        # Create the specification of deployment
        spec = client.V1JobSpec(
            template=template,
            parallelism=workers,
            backoff_limit=4)
        # Instantiate the job object
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name="transformer-" + request_id),
            spec=spec)

        return job

    def create_job(self, api_instance, job, namespace):
        # Create job
        api_response = api_instance.create_namespaced_job(
            body=job,
            namespace=namespace)
        print("Job created. status='%s'" % str(api_response.status))

    def launch_transformer_jobs(self, image, request_id, workers, chunk_size,
                                rabbitmq_uri, namespace):
        batch_v1 = client.BatchV1Api()
        job = self.create_job_object(request_id, image, chunk_size, rabbitmq_uri, workers)
        self.create_job(batch_v1, job, namespace)

    def shutdown_transformer_job(self, request_id, namespace):
        batch_v1 = client.BatchV1Api()

        # Make sure when we delete the job, the pods go away too
        # https://github.com/kubernetes-client/python/issues/234
        body = client.V1DeleteOptions(propagation_policy='Background')

        batch_v1.delete_namespaced_job(name="transformer-" + request_id,
                                       body=body,
                                       namespace=namespace)
