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
import os
from flask import current_app
from kubernetes import client
from kubernetes.client.rest import ApiException
from typing import Optional

from servicex_app.models import TransformRequest


class TransformerManager:
    POSIX_VOLUME_MOUNT = "/posix_volume"

    # This is the number of seconds tha thte transformer has to finish uploading
    # objects to the object store before it is terminated.
    POD_TERMINATION_GRACE_PERIOD = 5*60

    @classmethod
    def make_api(cls, rabbitmq_adaptor):
        cls.rabbitmq_adaptor = rabbitmq_adaptor
        return cls

    def __init__(self, manager_mode):
        if manager_mode == 'internal-kubernetes':
            kubernetes.config.load_incluster_config()
        elif manager_mode == 'external-kubernetes':
            kubernetes.config.load_kube_config()
        else:
            current_app.logger.error(f"Manager mode {manager_mode} not valid")
            raise ValueError('Manager mode '+manager_mode+' not valid')

    def start_transformers(self, config: dict, request_rec: TransformRequest):
        """
        Start the transformers for a given request
        """
        rabbitmq_uri = config['TRANSFORMER_RABBIT_MQ_URL']
        namespace = config['TRANSFORMER_NAMESPACE']
        x509_secret = config['TRANSFORMER_X509_SECRET']
        generated_code_cm = request_rec.generated_code_cm

        request_rec.workers = min(max(1, request_rec.files), request_rec.workers)

        current_app.logger.info(
            f"Launching {request_rec.workers} transformers.",
            extra={'requestId': request_rec.request_id})

        self.launch_transformer_jobs(
            image=request_rec.image, request_id=request_rec.request_id,
            workers=request_rec.workers,
            rabbitmq_uri=rabbitmq_uri,
            namespace=namespace,
            x509_secret=x509_secret,
            generated_code_cm=generated_code_cm,
            result_destination=request_rec.result_destination,
            result_format=request_rec.result_format,
            transformer_language=request_rec.transformer_language,
            transformer_command=request_rec.transformer_command
        )

    @staticmethod
    def create_job_object(request_id, image, rabbitmq_uri, workers,
                          result_destination, result_format, x509_secret,
                          generated_code_cm, transformer_language, transformer_command):
        volume_mounts = []
        volumes = []

        # append sidecar volume
        output_path = current_app.config['TRANSFORMER_SIDECAR_VOLUME_PATH']
        volume_mounts.append(
            client.V1VolumeMount(
                name='sidecar-volume',
                mount_path=output_path)
        )

        volumes.append(
            client.V1Volume(
                name='sidecar-volume',
                empty_dir=client.V1EmptyDirVolumeSource())
        )

        if x509_secret:
            volume_mounts.append(
                client.V1VolumeMount(
                    name='x509-secret',
                    mount_path='/etc/grid-security-ro')
            )
            volumes.append(client.V1Volume(
                name='x509-secret',
                secret=client.V1SecretVolumeSource(secret_name=x509_secret)
            ))

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

        # provide pods with level and logging server info
        env += [
            client.V1EnvVar("LOG_LEVEL", value=os.environ.get('LOG_LEVEL', 'INFO').upper()),
            client.V1EnvVar("LOGSTASH_HOST", value=os.environ.get('LOGSTASH_HOST')),
            client.V1EnvVar("LOGSTASH_PORT", value=os.environ.get('LOGSTASH_PORT'))
        ]

        # Provide each pod with an environment var holding that pod's name
        pod_name_value_from = client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(
                field_path="metadata.name"))
        host_name_value_from = client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(
                field_path="spec.nodeName"))
        env += [
            client.V1EnvVar("POD_NAME", value_from=pod_name_value_from),
            client.V1EnvVar("HOST_NAME", value_from=host_name_value_from)
        ]

        # Provide each pod with an environment var holding that instance name
        if "INSTANCE_NAME" in current_app.config:
            instance_name = current_app.config['INSTANCE_NAME']
            env_var_instance_name = client.V1EnvVar("INSTANCE_NAME",
                                                    value=instance_name)
            env = env + [env_var_instance_name]

        # provide each pod with an environment var holding cache prefix path
        if "TRANSFORMER_CACHE_PREFIX" in current_app.config:
            env += [client.V1EnvVar("CACHE_PREFIX",
                                    value=current_app.config["TRANSFORMER_CACHE_PREFIX"])]

        if result_destination == 'object-store':
            env = env + [
                client.V1EnvVar(name='MINIO_URL',
                                value=current_app.config['MINIO_URL_TRANSFORMER']),
                client.V1EnvVar(name='MINIO_ACCESS_KEY',
                                value=current_app.config['MINIO_ACCESS_KEY']),
                client.V1EnvVar(name='MINIO_SECRET_KEY',
                                value=current_app.config['MINIO_SECRET_KEY']),
            ]
            if 'MINIO_ENCRYPT' in current_app.config:
                env += [client.V1EnvVar(name='MINIO_ENCRYPT',
                                        value=str(current_app.config['MINIO_ENCRYPT']))]

        if result_destination == 'volume':
            TransformerManager.create_posix_volume(volumes, volume_mounts)

        science_command = " "
        if x509_secret:
            science_command = "until [ -f /servicex/output/scripts/proxy-exporter.sh ];" \
                              "do sleep 5;done &&" \
                              " /servicex/output/scripts/proxy-exporter.sh & sleep 5 && "

        sidecar_command = "PYTHONPATH=/servicex/transformer_sidecar:$PYTHONPATH " + \
            "python /servicex/transformer_sidecar/transformer.py " + \
            " --shared-dir /servicex/output " + \
            " --request-id " + request_id + \
            " --rabbit-uri " + rabbitmq_uri + \
            " --result-destination " + result_destination + \
            " --result-format " + result_format

        watch_path = os.path.join(current_app.config['TRANSFORMER_SIDECAR_VOLUME_PATH'],
                                  request_id)
        science_command += "cp /generated/transformer_capabilities.json {op} && " \
                           "PYTHONPATH=/generated:$PYTHONPATH " \
                           "bash {op}/scripts/watch.sh ".format(op=output_path) + \
                           "{TL} ".format(TL=transformer_language) + \
                           "{TC} ".format(TC=transformer_command) + \
                           watch_path

        if result_destination == 'volume':
            sidecar_command += " --output-dir " + os.path.join(
                TransformerManager.POSIX_VOLUME_MOUNT,
                current_app.config['TRANSFORMER_PERSISTENCE_SUBDIR'])

        resources = client.V1ResourceRequirements(
            limits={"cpu": current_app.config['TRANSFORMER_CPU_LIMIT']}
        )

        # Configure Pod template container
        science_container = client.V1Container(
            name="transformer",
            image=image,
            image_pull_policy=current_app.config['TRANSFORMER_SCIENCE_IMAGE_PULL_POLICY'],
            volume_mounts=volume_mounts,
            command=["bash", "-c"],
            env=env,
            args=[science_command],
            resources=resources
        )

        # Configure Pod template container
        sidecar = client.V1Container(
            name="sidecar",
            image=current_app.config['TRANSFORMER_SIDECAR_IMAGE'],
            image_pull_policy=current_app.config['TRANSFORMER_SIDECAR_PULL_POLICY'],
            volume_mounts=volume_mounts,
            command=["bash", "-c"],
            env=env,
            args=[sidecar_command],
            resources=resources
        )

        # Create and Configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={'app': "transformer-" + request_id}),
            spec=client.V1PodSpec(
                restart_policy="Always",
                termination_grace_period_seconds=TransformerManager.POD_TERMINATION_GRACE_PERIOD,
                priority_class_name=current_app.config.get('TRANSFORMER_PRIORITY_CLASS', None),
                containers=[sidecar, science_container],  # Containers are started in this order
                volumes=volumes))

        # Create the specification of deployment
        selector = client.V1LabelSelector(
            match_labels={
                "app": "transformer-" + request_id
            })

        # If we are using Autoscaler then always start with one replica
        if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED']:
            replicas = current_app.config.get('TRANSFORMER_MIN_REPLICAS', 1)
        else:
            replicas = workers
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
    def create_posix_volume(volumes, volume_mounts):
        if 'TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM' not in current_app.config or \
                not current_app.config['TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM']:
            empty_dir = client.V1Volume(
                name='posix-volume',
                empty_dir=client.V1EmptyDirVolumeSource())
            volumes.append(empty_dir)
        else:
            volumes.append(
                client.V1Volume(
                    name='posix-volume',
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=current_app.config['TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM']
                    )
                )
            )

        volume_mounts.append(
            client.V1VolumeMount(mount_path=TransformerManager.POSIX_VOLUME_MOUNT,
                                 name='posix-volume'))

    def persistent_volume_claim_exists(self, claim_name, namespace):
        api = client.CoreV1Api()

        pvcs = api.list_namespaced_persistent_volume_claim(namespace=namespace, watch=False)
        for pvc in pvcs.items:
            if pvc.metadata.name == claim_name:
                if pvc.status.phase == 'Bound':
                    return True
                else:
                    current_app.logger.warning(f"Volume Claim '{claim_name} found, "
                                               f"but it is not bound")
                    return False
        return False

    @staticmethod
    def create_hpa_object(request_id):
        target = client.V1CrossVersionObjectReference(
            api_version="apps/v1",
            kind='Deployment',
            name="transformer-" + request_id
        )

        cfg = current_app.config
        spec = client.V1HorizontalPodAutoscalerSpec(
            scale_target_ref=target,
            target_cpu_utilization_percentage=cfg["TRANSFORMER_CPU_SCALE_THRESHOLD"],
            min_replicas=cfg["TRANSFORMER_MIN_REPLICAS"],
            max_replicas=cfg["TRANSFORMER_MAX_REPLICAS"]
        )
        hpa = client.V1HorizontalPodAutoscaler(
            api_version="autoscaling/v1",
            kind='HorizontalPodAutoscaler',
            metadata=client.V1ObjectMeta(name="transformer-" + request_id),
            spec=spec
        )

        return hpa

    @staticmethod
    def _create_job(api_instance, job, namespace):
        try:
            api_instance.create_namespaced_deployment(body=job, namespace=namespace)
            current_app.logger.info("Request deployment created.")
        except ApiException as e:
            current_app.logger.exception(f"Exception during HPA Creation: {e}")

    @staticmethod
    def _create_hpa(api_instance, hpa, namespace):
        try:
            api_instance.create_namespaced_horizontal_pod_autoscaler(
                body=hpa,
                namespace=namespace)
            current_app.logger.info("HPA created.")
        except ApiException as e:
            current_app.logger.exception(f"Exception during HPA Creation: {e}")

    def launch_transformer_jobs(self, image, request_id, workers,
                                rabbitmq_uri, namespace, x509_secret, generated_code_cm,
                                result_destination, result_format, transformer_language,
                                transformer_command
                                ):
        api_v1 = client.AppsV1Api()
        job = self.create_job_object(request_id, image, rabbitmq_uri, workers,
                                     result_destination, result_format,
                                     x509_secret, generated_code_cm,
                                     transformer_language, transformer_command)

        self._create_job(api_v1, job, namespace)

        if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED']:
            autoscaler_api = kubernetes.client.AutoscalingV1Api()
            hpa = self.create_hpa_object(request_id)
            self._create_hpa(autoscaler_api, hpa, namespace)

    @classmethod
    def shutdown_transformer_job(cls, request_id, namespace):
        try:
            if current_app.config['TRANSFORMER_AUTOSCALE_ENABLED']:
                autoscaler_api = kubernetes.client.AutoscalingV1Api()
                autoscaler_api.delete_namespaced_horizontal_pod_autoscaler(
                    name="transformer-" + request_id,
                    namespace=namespace
                )
        except ApiException:
            current_app.logger.exception("Exception during Job HPA Shut Down", extra={
                                         "requestId": request_id})

        try:
            api_core = client.CoreV1Api()
            configmap_name = "{}-generated-source".format(request_id)
            api_core.delete_namespaced_config_map(name=configmap_name,
                                                  namespace=namespace)
        except ApiException:
            current_app.logger.exception("Exception during Job ConfigMap cleanup", extra={
                                         "requestId": request_id})

        try:
            api_v1 = client.AppsV1Api()
            api_v1.delete_namespaced_deployment(
                name="transformer-" + request_id,
                namespace=namespace
            )
        except ApiException:
            current_app.logger.exception("Exception during Job Deployment Shut Down", extra={
                                         "requestId": request_id})

        # delete RabbitMQ queue
        try:
            current_app.logger.info(f"Deleting queue transformer-{request_id}")
            cls.rabbitmq_adaptor.delete_queue(f"transformer-{request_id}")
        except Exception as e:
            current_app.logger.exception("Exception during Job Queue Deletion", extra={
                "requestId": request_id,
                "exception": e
            })

    @staticmethod
    def get_deployment_status(
        request_id: str
    ) -> Optional[kubernetes.client.models.v1_deployment_status.V1DeploymentStatus]:
        namespace = current_app.config["TRANSFORMER_NAMESPACE"]
        api = client.AppsV1Api()
        selector = f"metadata.name=transformer-{request_id}"
        results: kubernetes.client.AppsV1beta1DeploymentList
        results = api.list_namespaced_deployment(namespace, field_selector=selector)
        if not results.items:
            return None
        deployment: kubernetes.client.AppsV1beta1Deployment = results.items[0]
        return deployment.status

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
