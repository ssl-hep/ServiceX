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
import base64

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

    @staticmethod
    def create_job_object(request_id, image, chunk_size, rabbitmq_uri, workers,
                          result_destination, result_format, x509_secret, kafka_broker,
                          generated_code_cm):
        volume_mounts = [
            client.V1VolumeMount(
                name='x509-secret',
                mount_path='/etc/grid-security-ro')
        ]

        volumes = [
            client.V1Volume(
                name='x509-secret',
                secret=client.V1SecretVolumeSource(secret_name=x509_secret)
            )
        ]

        if generated_code_cm:
            volumes.append(client.V1Volume(
                name='generated-code',
                config_map=client.V1ConfigMapVolumeSource(
                    name=generated_code_cm)
                )
            )
            volume_mounts.append(
                client.V1VolumeMount(mount_path="/generated", name='generated-code'))

        if "TRANSFORMER_LOCAL_PATH" in current_app.config:
            path = current_app.config['TRANSFORMER_LOCAL_PATH']
            volumes.append(client.V1Volume(
                name='rootfiles',
                host_path=client.V1HostPathVolumeSource(path=path)))
            volume_mounts.append(
                client.V1VolumeMount(mount_path="/data", name='rootfiles'))

        # Compute Environment Vars
        env = [client.V1EnvVar(name="BASH_ENV", value="/servicex/.bashrc")]

        # Provide each pod with an environment var holding that pod's name
        pod_name_value_from = client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(
                field_path="metadata.name"))
        env_var_pod_name = client.V1EnvVar("POD_NAME", value_from=pod_name_value_from)

        env = env + [env_var_pod_name]

        if result_destination == 'object-store':
            env = env + [
                client.V1EnvVar(name='MINIO_URL',
                                value=current_app.config['MINIO_URL_TRANSFORMER']),
                client.V1EnvVar(name='MINIO_ACCESS_KEY',
                                value=current_app.config['MINIO_ACCESS_KEY']),
                client.V1EnvVar(name='MINIO_SECRET_KEY',
                                value=current_app.config['MINIO_SECRET_KEY']),
            ]

        python_args = ["/servicex/proxy-exporter.sh & sleep 5 && " +
                       "PYTHONPATH=/generated:$PYTHONPATH " +
                       "python /servicex/transformer.py " +
                       " --request-id " + request_id +
                       " --rabbit-uri " + rabbitmq_uri +
                       " --chunks " + str(chunk_size) +
                       " --result-destination " + result_destination +
                       " --result-format " + result_format]

        if kafka_broker:
            python_args[0] += " --brokerlist "+kafka_broker

        resources = client.V1ResourceRequirements(
            limits={"cpu": current_app.config['TRANSFORMER_CPU_LIMIT']}
        )
        # Configure Pod template container
        container = client.V1Container(
            name="transformer-" + request_id,
            image=image,
            image_pull_policy=current_app.config['TRANSFORMER_PULL_POLICY'],
            volume_mounts=volume_mounts,
            command=["bash", "-c"],  # Can't get bash to pick up my .bashrc!
            env=env,
            args=python_args,
            resources=resources
        )

        # Create and Configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={'app': "transformer-" + request_id}),
            spec=client.V1PodSpec(
                restart_policy="Always",
                containers=[container],
                volumes=volumes))

        # Create the specification of deployment
        selector = client.V1LabelSelector(
            match_labels={
                "app": "transformer-" + request_id
            })

        # If we are using Autoscaler then always start with one replica
        replicas = 1 if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED'] else workers
        spec = client.V1DeploymentSpec(
            template=template,
            selector=selector,
            replicas=replicas
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name="transformer-" + request_id),
            spec=spec
        )

        return deployment

    @staticmethod
    def create_hpa_object(request_id, workers):
        target = client.V1CrossVersionObjectReference(
            api_version="apps/v1",
            kind='Deployment',
            name="transformer-" + request_id
        )

        hpa = client.V1HorizontalPodAutoscaler(
            api_version="autoscaling/v1",
            kind='HorizontalPodAutoscaler',
            metadata=client.V1ObjectMeta(name="transformer-" + request_id),
            spec=client.V1HorizontalPodAutoscalerSpec(
                max_replicas=workers,
                scale_target_ref=target,
                target_cpu_utilization_percentage=current_app.config['TRANSFORMER_CPU_LIMIT']
            )
        )

        return hpa

    @staticmethod
    def _create_job(api_instance, job, namespace):
        # Create job

        api_response = api_instance.create_namespaced_deployment(
            body=job,
            namespace=namespace)
        print("Job created. status='%s'" % str(api_response.status))

    @staticmethod
    def _create_hpa(api_instance, hpa, namespace):
        # Create job
        api_response = api_instance.create_namespaced_horizontal_pod_autoscaler(
            body=hpa,
            namespace=namespace)
        print("Job created. status='%s'" % str(api_response.status))

    def launch_transformer_jobs(self, image, request_id, workers, chunk_size,
                                rabbitmq_uri, namespace, x509_secret, generated_code_cm,
                                result_destination, result_format, kafka_broker=None,
                                ):
        api_v1 = client.AppsV1Api()
        job = self.create_job_object(request_id, image, chunk_size, rabbitmq_uri, workers,
                                     result_destination, result_format,
                                     x509_secret, kafka_broker, generated_code_cm)

        self._create_job(api_v1, job, namespace)

        if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED']:
            autoscaler_api = kubernetes.client.AutoscalingV1Api()
            hpa = self.create_hpa_object(request_id, workers)
            self._create_hpa(autoscaler_api, hpa, namespace)

    @staticmethod
    def shutdown_transformer_job(request_id, namespace):
        if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED']:
            autoscaler_api = kubernetes.client.AutoscalingV1Api()
            autoscaler_api.delete_namespaced_horizontal_pod_autoscaler(
                name="transformer-" + request_id,
                namespace=namespace
            )

        api_v1 = client.AppsV1Api()
        api_v1.delete_namespaced_deployment(
            name="transformer-" + request_id,
            namespace=namespace
        )

    @staticmethod
    def create_configmap_from_zip(zipfile, request_id, namespace):
        configmap_name = "{}-generated-source".format(request_id)
        data = {
            file.filename:
                base64.b64encode(zipfile.open(file).read()).decode("ascii") for file in
            zipfile.filelist
        }

        metadata = client.V1ObjectMeta(
            name=configmap_name,
            namespace=namespace,
        )

        # Instantiate the configmap object
        configmap = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            binary_data=data,
            metadata=metadata
        )

        api_instance = client.CoreV1Api()
        api_instance.create_namespaced_config_map(
            namespace=namespace,
            body=configmap)
        return configmap_name
