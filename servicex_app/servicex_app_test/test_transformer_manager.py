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
import re
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import servicex_app
from servicex_app.models import TransformRequest, TransformStatus
from servicex_app.transformer_manager import TransformerManager
from servicex_app_test.resource_test_base import ResourceTestBase


def _arg_value(args, param):
    return re.search(param + " (\\S+)", args[0]).group(1)


def _env_value(env_list, env_name):
    return [x for x in env_list if x.name == env_name][0].value


# Base configuration shared across most transformer manager tests
BASE_TRANSFORMER_CONFIG = {
    "OBJECT_STORE_ENABLED": True,
    "MINIO_URL_TRANSFORMER": "rolling-snail-minio:9000",
    "MINIO_ACCESS_KEY": "itsame",
    "MINIO_SECRET_KEY": "shhh",
    "TRANSFORMER_CPU_LIMIT": 1,
    "TRANSFORMER_MEMORY_LIMIT": "2Gi",
    "TRANSFORMER_CPU_REQUEST": "500m",
    "TRANSFORMER_MEMORY_REQUEST": "512Mi",
    "TRANSFORMER_CPU_SCALE_THRESHOLD": 30,
    "TRANSFORMER_SIDECAR_VOLUME_PATH": "/servicex/output",
    "TRANSFORMER_SIDECAR_IMAGE": "pondd/servicex_yt_transformer:sidecar",
    "TRANSFORMER_SIDECAR_PULL_POLICY": "Always",
    "TRANSFORMER_SCIENCE_IMAGE_PULL_POLICY": "Always",
    "TRANSFORMER_CVMFS_VOLUME": None,
}


def make_config(**overrides):
    """Create a config dict based on BASE_TRANSFORMER_CONFIG with overrides."""
    return {**BASE_TRANSFORMER_CONFIG, **overrides}


class TestTransformerManager(ResourceTestBase):

    @pytest.fixture
    def mock_kubernetes(self, mocker):
        mock_kubernetes = mocker.Mock(name="mock_kubernetes")
        mocker.patch("servicex_app.transformer_manager.kubernetes", mock_kubernetes)
        mocker.patch("servicex_app.transformer_manager.client", mock_kubernetes.client)
        return mock_kubernetes

    @pytest.fixture
    def transformer_manager(self, mocker):
        mock_kubernetes = mocker.Mock(name="mock_kubernetes")
        mocker.patch("servicex_app.transformer_manager.kubernetes", mock_kubernetes)
        mocker.patch("servicex_app.transformer_manager.client", mock_kubernetes.client)

        return mock_kubernetes

        """
            mock_transform_manager. \
                start_transformers \
                .assert_called_with(image=submitted_request.image,
                                    request_id=submitted_request.request_id,
                                    workers=submitted_request.workers,
                                    max_workers=submitted_request.files,
                                    generated_code_cm=submitted_request.generated_code_cm,
                                    rabbitmq_uri='amqp://trans.rabbit',
                                    namespace='my-ws',
                                    result_destination=submitted_request.result_destination,
                                    result_format=submitted_request.result_format,
                                    transformer_command=None,
                                    transformer_language=None,
                                    x509_secret='my-x509-secret')

    """

    def test_init_external_kubernetes(self, mock_kubernetes):
        TransformerManager("external-kubernetes")
        mock_kubernetes.config.load_kube_config.assert_called()

    def test_init_internal_kubernetes(self, mock_kubernetes):
        TransformerManager("internal-kubernetes")
        mock_kubernetes.config.load_incluster_config.assert_called()

    def test_init_invalid_config(self, mock_kubernetes):
        with pytest.raises(ValueError):
            TransformerManager("foo")
            mock_kubernetes.config.load_incluster_config.assert_not_called()
            mock_kubernetes.config.load_kube_config.assert_not_called()

    @pytest.mark.skip(reason="Needs to be updated to work with sidecar")
    def test_launch_transformer_jobs(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_api = mocker.patch.object(kubernetes.client, "AppsV1Api")
        mock_core_api = mocker.patch.object(kubernetes.client, "CoreV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        mock_core_api.list_namespaced_persistent_volume_claim = mocker.Mock(
            return_value=[]
        )

        transformer = TransformerManager("external-kubernetes")
        cfg = make_config(
            TRANSFORMER_CPU_LIMIT=4,
            TRANSFORMER_MIN_REPLICAS=3,
            TRANSFORMER_MAX_REPLICAS=17,
        )

        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)
        client = self._test_client(transformation_manager=transformer, extra_config=cfg)

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
            )
            called_deployment = mock_api.mock_calls[1][2]["body"]
            assert called_deployment.spec.replicas == cfg["TRANSFORMER_MIN_REPLICAS"]
            assert len(called_deployment.spec.template.spec.containers) == 2
            container = called_deployment.spec.template.spec.containers[0]
            assert container.image == "sslhep/servicex-transformer:pytest"
            assert container.image_pull_policy == "Always"
            assert len(container.volume_mounts) == 2
            assert container.volume_mounts[1].name == "x509-secret"
            assert container.volume_mounts[1].mount_path == "/etc/grid-security-ro"
            args = container.args

            # Note this test fails with the new sidecar implementation
            # TODO: Fix this
            assert args[0].startswith("/servicex/proxy-exporter.sh & sleep 5 && ")
            assert _arg_value(args, "--rabbit-uri") == "ampq://test.com"
            assert _arg_value(args, "--result-destination") == "object-store"

            limits = container.resources.limits
            assert "cpu" in limits
            assert limits["cpu"] == 4

            assert mock_api.mock_calls[1][2]["namespace"] == "my-ns"
            mock_autoscaling.create_namespaced_horizontal_pod_autoscaler.assert_called()
            autoscaling_spec = mock_autoscaling.mock_calls[0][2]["body"].spec
            assert autoscaling_spec.min_replicas == 3
            assert autoscaling_spec.max_replicas == 17
            assert autoscaling_spec.scale_target_ref.name == "transformer-1234"
            assert autoscaling_spec.target_cpu_utilization_percentage == 30

            assert len(called_deployment.spec.template.spec.volumes) == 2
            volume = called_deployment.spec.template.spec.volumes[1].secret
            assert volume.secret_name == "x509"

    def test_launch_transformer_jobs_no_autoscaler(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_api = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        cfg = make_config(TRANSFORMER_AUTOSCALE_ENABLED=False)
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(extra_config=cfg, transformation_manager=transformer)

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_deployment = mock_api.mock_calls[1][2]["body"]
            assert called_deployment.spec.replicas == 17
            mock_autoscaling.create_namespaced_horizontal_pod_autoscaler.assert_not_called()

            # Verify resource limits and requests are set
            container = called_deployment.spec.template.spec.containers[0]
            limits = container.resources.limits
            assert limits["cpu"] == 1
            assert limits["memory"] == "2Gi"
            requests = container.resources.requests
            assert requests["cpu"] == "500m"
            assert requests["memory"] == "512Mi"

    def test_launch_transformer_with_hostpath(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(TRANSFORMER_LOCAL_PATH="/tmp/foo"),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )

            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            assert container.volume_mounts[1].mount_path == "/etc/grid-security-ro"
            assert called_job.spec.template.spec.volumes[1].secret.secret_name == "x509"

            assert container.volume_mounts[2].mount_path == "/data"
            assert called_job.spec.template.spec.volumes[2].host_path.path == "/tmp/foo"

    def test_launch_transformer_jobs_with_generated_code(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")
        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(), transformation_manager=transformer
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm="my-config-map",
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            config_map_vol_mount = container.volume_mounts[2]
            assert config_map_vol_mount.name == "generated-code"
            assert config_map_vol_mount.mount_path == "/generated"

            config_map_vol = called_job.spec.template.spec.volumes[2]
            assert config_map_vol.name == "generated-code"
            assert config_map_vol.config_map.name == "my-config-map"

    def test_launch_transformer_jobs_with_object_store(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")
        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(), transformation_manager=transformer
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            args = container.args
            assert _arg_value(args, "--result-destination") == "object-store"
            assert _arg_value(args, "--result-format") == "parquet"

            env = container.env
            assert _env_value(env, "MINIO_URL") == "rolling-snail-minio:9000"
            assert _env_value(env, "MINIO_ACCESS_KEY") == "itsame"
            assert _env_value(env, "MINIO_SECRET_KEY") == "shhh"

    def test_launch_transformer_jobs_with_object_store_and_xcache(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")
        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(TRANSFORMER_CACHE_PREFIX="root://dummy"),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            args = container.args
            assert _arg_value(args, "--result-destination") == "object-store"
            assert _arg_value(args, "--result-format") == "parquet"

            env = container.env
            assert _env_value(env, "MINIO_URL") == "rolling-snail-minio:9000"
            assert _env_value(env, "MINIO_ACCESS_KEY") == "itsame"
            assert _env_value(env, "MINIO_SECRET_KEY") == "shhh"
            assert _env_value(env, "CACHE_PREFIX") == "root://dummy"

    def test_launch_transformer_jobs_with_secure_object_store(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")
        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(MINIO_ENCRYPT="True"),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            args = container.args
            assert _arg_value(args, "--result-destination") == "object-store"
            assert _arg_value(args, "--result-format") == "parquet"

            env = container.env
            assert _env_value(env, "MINIO_URL") == "rolling-snail-minio:9000"
            assert _env_value(env, "MINIO_ACCESS_KEY") == "itsame"
            assert _env_value(env, "MINIO_SECRET_KEY") == "shhh"
            assert _env_value(env, "MINIO_ENCRYPT") == "True"

    def test_launch_transformer_jobs_with_provided_claim(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(
                OBJECT_STORE_ENABLED=False,
                TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM="my-pvc",
                TRANSFORMER_PERSISTENCE_SUBDIR="output-data",
                TRANSFORMER_AUTOSCALE_ENABLED=False,
            ),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="volume",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            args = container.args
            assert _arg_value(args, "--result-destination") == "volume"
            assert (
                _arg_value(args, "--output-dir")
                == "/posix_volume" + os.sep + "output-data"
            )
            assert _arg_value(args, "--result-format") == "parquet"

            posix_vol = next(
                filter(
                    lambda v: v.name == "posix-volume",
                    called_job.spec.template.spec.volumes,
                )
            )
            assert posix_vol.persistent_volume_claim.claim_name == "my-pvc"

            posix_vol_mount = next(
                filter(lambda m: m.name == "posix-volume", container.volume_mounts)
            )
            assert posix_vol_mount.mount_path == "/posix_volume"

    def test_launch_transformer_jobs_with_posix_emptydir(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(
                OBJECT_STORE_ENABLED=False,
                TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM=None,
                TRANSFORMER_PERSISTENCE_SUBDIR="output-data",
                TRANSFORMER_AUTOSCALE_ENABLED=False,
            ),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="volume",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]
            args = container.args
            assert _arg_value(args, "--result-destination") == "volume"
            assert (
                _arg_value(args, "--output-dir")
                == "/posix_volume" + os.sep + "output-data"
            )
            assert _arg_value(args, "--result-format") == "parquet"

            posix_vol = next(
                filter(
                    lambda v: v.name == "posix-volume",
                    called_job.spec.template.spec.volumes,
                )
            )
            assert posix_vol.empty_dir

            posix_vol_mount = next(
                filter(lambda m: m.name == "posix-volume", container.volume_mounts)
            )
            assert posix_vol_mount.mount_path == "/posix_volume"

    def test_launch_transformer_jobs_no_certs(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_api = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            transformation_manager=transformer,
            extra_config=make_config(
                TRANSFORMER_CPU_LIMIT=4,
                TRANSFORMER_MIN_REPLICAS=3,
                TRANSFORMER_MAX_REPLICAS=17,
                TRANSFORMER_X509_SECRET=None,
            ),
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret=None,
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_deployment = mock_api.mock_calls[1][2]["body"]
            assert len(called_deployment.spec.template.spec.containers) == 2
            container = called_deployment.spec.template.spec.containers[0]
            assert len(container.volume_mounts) == 1
            assert len(called_deployment.spec.template.spec.volumes) == 1
            args = container.args
            assert not args[0].startswith("/servicex/proxy-exporter.sh & sleep 5 && ")

    def test_shutdown_transformer_jobs(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")

        mock_api = mocker.MagicMock(kubernetes.client.AppsV1Api)
        mocker.patch.object(kubernetes.client, "AppsV1Api", return_value=mock_api)

        mock_core_api = mocker.MagicMock(kubernetes.client.CoreV1Api)
        mocker.patch.object(kubernetes.client, "CoreV1Api", return_value=mock_core_api)

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(transformation_manager=transformer)

        with client.application.app_context():
            transformer.shutdown_transformer_job("1234", "my-ns")
            mock_api.delete_namespaced_deployment.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )
            mock_core_api.delete_namespaced_config_map.assert_called_with(
                name="1234-generated-source", namespace="my-ns"
            )
            mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )

    def test_shutdown_transformer_jobs_exceptions(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")

        mock_api = mocker.MagicMock(kubernetes.client.AppsV1Api)
        mocker.patch.object(kubernetes.client, "AppsV1Api", return_value=mock_api)
        mock_api.delete_namespaced_deployment.side_effect = (
            kubernetes.client.rest.ApiException()
        )

        mock_core_api = mocker.MagicMock(kubernetes.client.CoreV1Api)
        mocker.patch.object(kubernetes.client, "CoreV1Api", return_value=mock_core_api)
        mock_core_api.delete_namespaced_config_map.side_effect = (
            kubernetes.client.rest.ApiException()
        )

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )
        mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.side_effect = (
            kubernetes.client.rest.ApiException()
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)
        transformer.celery_app.control.cancel_consumer = mocker.MagicMock(
            side_effect=Exception()
        )

        client = self._test_client(transformation_manager=transformer)
        client.application.logger = mocker.MagicMock()

        # default mode with exceptions
        with client.application.app_context():
            transformer.shutdown_transformer_job("1234", "my-ns")
            mock_api.delete_namespaced_deployment.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )
            mock_core_api.delete_namespaced_config_map.assert_called_with(
                name="1234-generated-source", namespace="my-ns"
            )
            mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )
            transformer.celery_app.control.cancel_consumer.assert_called_with(
                "transformer-1234"
            )
        assert client.application.logger.exception.call_count == 4

        # now check quiet mode
        client.application.logger.exception.reset_mock()
        with client.application.app_context():
            transformer.shutdown_transformer_job("1234", "my-ns", True)
            mock_api.delete_namespaced_deployment.assert_called_with(
                name="transformer-1234",
                namespace="my-ns",
            )
            mock_core_api.delete_namespaced_config_map.assert_called_with(
                name="1234-generated-source",
                namespace="my-ns",
            )
            mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )
        client.application.logger.exception.assert_not_called()

    def test_shutdown_transformer_jobs_exceptions_once(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")

        mock_api = mocker.MagicMock(kubernetes.client.AppsV1Api)
        mocker.patch.object(kubernetes.client, "AppsV1Api", return_value=mock_api)
        mock_api.delete_namespaced_deployment.side_effect = (
            kubernetes.client.rest.ApiException(),
            None,
        )

        mock_core_api = mocker.MagicMock(kubernetes.client.CoreV1Api)
        mocker.patch.object(kubernetes.client, "CoreV1Api", return_value=mock_core_api)
        mock_core_api.delete_namespaced_config_map.side_effect = (
            kubernetes.client.rest.ApiException(),
            None,
        )

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )
        mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.side_effect = (
            kubernetes.client.rest.ApiException(),
            None,
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)
        transformer.celery_app.control.cancel_consumer = mocker.MagicMock()

        client = self._test_client(transformation_manager=transformer)
        client.application.logger = mocker.MagicMock()

        # default mode with exceptions
        with client.application.app_context():
            transformer.shutdown_transformer_job("1234", "my-ns")
            assert mock_api.delete_namespaced_deployment.call_count == 2
            assert mock_core_api.delete_namespaced_config_map.call_count == 2
            assert (
                mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.call_count
                == 2
            )
            assert client.application.logger.exception.call_count == 0

    def test_shutdown_transformer_jobs_no_autoscaler(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")

        mock_api = mocker.MagicMock(kubernetes.client.AppsV1Api)
        mocker.patch.object(kubernetes.client, "AppsV1Api", return_value=mock_api)

        mock_core_api = mocker.MagicMock(kubernetes.client.CoreV1Api)
        mocker.patch.object(kubernetes.client, "CoreV1Api", return_value=mock_core_api)

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.shutdown_transformer_job("1234", "my-ns")
            mock_api.delete_namespaced_deployment.assert_called_with(
                name="transformer-1234", namespace="my-ns"
            )
            mock_core_api.delete_namespaced_config_map.assert_called_with(
                name="1234-generated-source", namespace="my-ns"
            )
            mock_autoscaling.delete_namespaced_horizontal_pod_autoscaler.assert_not_called()

    def test_create_configmap_from_zip(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_api = mocker.MagicMock(kubernetes.client.CoreV1Api)
        mocker.patch.object(kubernetes.client, "CoreV1Api", return_value=mock_api)

        mock_create_namespaced_config_map = mocker.Mock()
        mock_api.create_namespaced_config_map = mock_create_namespaced_config_map

        transformer = TransformerManager("external-kubernetes")
        mock_zip = mocker.MagicMock(zipfile.ZipFile)
        mock_zip_ext = mocker.Mock()
        mock_zip_ext.filename = "foo.sh"
        mock_zip.filelist = [mock_zip_ext]
        mock_open = mocker.Mock()
        mock_open.read = mocker.Mock(return_value=b"hi there")
        mock_zip.open = mocker.Mock(return_value=mock_open)

        transformer.create_configmap_from_zip(mock_zip, "my-request", "servicex")

        mock_create_namespaced_config_map.assert_called()
        calls = mock_create_namespaced_config_map.call_args
        "foo.sh" in calls[1]["body"].binary_data.keys()
        assert calls[1]["body"].binary_data["foo.sh"] == base64.b64encode(
            b"hi there"
        ).decode("ascii")
        assert calls[1]["namespace"] == "servicex"
        assert calls[1]["body"].metadata.name == "my-request-generated-source"

    def test_get_deployment_status(self, mocker, mock_kubernetes):
        mock_api = mock_kubernetes.client.AppsV1Api.return_value
        mock_deployment_list = mocker.MagicMock(name="mock_deployment_list")
        mock_api.list_namespaced_deployment.return_value = mock_deployment_list
        mock_deployment = mocker.MagicMock(name="mock_deployment")
        mock_deployment_list.items = [mock_deployment]

        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=True
        )

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer_manager,
        )

        with client.application.app_context():
            status = transformer_manager.get_deployment_status("1234")
            assert status == mock_deployment.status

    def test_get_deployment_status_404(self, mocker, mock_kubernetes):
        mock_api = mock_kubernetes.client.AppsV1Api.return_value
        mock_deployment_list = mocker.MagicMock(name="mock_deployment_list")
        mock_api.list_namespaced_deployment.return_value = mock_deployment_list
        mock_deployment_list.items = []

        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=True
        )

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer_manager,
        )

        with client.application.app_context():
            status = transformer_manager.get_deployment_status("1234")
            assert status is None

    def test_persistent_claim_exists(self, mock_kubernetes, mocker):
        mock_coreV1 = mocker.Mock()
        mock_kubernetes.client.CoreV1Api = mocker.Mock(return_value=mock_coreV1)

        mock_persistent_volume_claims = SimpleNamespace()
        mock_persistent_volume_claims.items = [
            SimpleNamespace(
                metadata=SimpleNamespace(name="foo"),
                status=SimpleNamespace(phase="Bound"),
            ),
            SimpleNamespace(
                metadata=SimpleNamespace(name="bar"),
                status=SimpleNamespace(phase="Unbound"),
            ),
        ]
        mock_coreV1.list_namespaced_persistent_volume_claim = mocker.Mock(
            return_value=mock_persistent_volume_claims
        )

        test_transformer_manager = TransformerManager("external-kubernetes")

        assert test_transformer_manager.persistent_volume_claim_exists("foo", "my-ns")
        mock_coreV1.list_namespaced_persistent_volume_claim.assert_called_with(
            namespace="my-ns", watch=False
        )
        assert not test_transformer_manager.persistent_volume_claim_exists(
            "bar", "my-ns"
        )
        assert not test_transformer_manager.persistent_volume_claim_exists(
            "baz", "my-ns"
        )

    def test_die_when_claim_missing(self, mocker, mock_kubernetes):
        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=False
        )

        mock_exit = mocker.Mock()
        mocker.patch("servicex_app.sys.exit", mock_exit)

        client = self._test_client(transformation_manager=transformer_manager)

        with client.application.app_context():
            mock_exit.assert_called_with(-1)

    def test_cache_vps_configuration(self, mocker):
        import kubernetes
        import json

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(
                TRANSFORMER_LOCAL_PATH="/tmp/foo",
                TRANSFORMER_CACHE_PREFIX="root://dummy",  # this should be overwritten
                TRANSFORMER_CACHE_VPS_SITE="MWT2",
                TRANSFORMER_CACHE_VPS_LIVENESS_URL="https://dummy",
            ),
            transformation_manager=transformer,
        )

        request_func_mock = mocker.patch("urllib3.request")
        request_func_mock.return_value.json.return_value = json.loads("""
{
  "MWT2": {
    "xcache-uc-1": {
      "site": "MWT2",
      "id": "xcache-uc-1",
      "address": "1.1.1.1:1094",
      "size": "34365115224",
      "timestamp": 1759633484503,
      "live": true
    },
    "xcache-uc-2": {
      "site": "MWT2",
      "id": "xcache-uc-2",
      "address": "1.1.1.2:1094",
      "size": "35927165916",
      "timestamp": 1759633466503,
      "live": true
    },
    "xcache-uc-3": {
      "site": "MWT2",
      "id": "xcache-uc-3",
      "address": "1.1.1.3:1094",
      "size": "185222398084",
      "timestamp": 1759633472603,
      "live": true
    }
  }
}""")

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]

            env = container.env
            request_func_mock.assert_called_with("GET", "https://dummy")
            assert (
                _env_value(env, "CACHE_PREFIX")
                == "1.1.1.1:1094,1.1.1.2:1094,1.1.1.3:1094"
            )

    def test_cache_vps_configuration_bad_site(self, mocker):
        import kubernetes
        import json

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(
                TRANSFORMER_LOCAL_PATH="/tmp/foo",
                TRANSFORMER_CACHE_PREFIX="root://dummy",  # this should NOT be overwritten
                TRANSFORMER_CACHE_VPS_SITE="MWT3",
                TRANSFORMER_CACHE_VPS_LIVENESS_URL="https://dummy",
            ),
            transformation_manager=transformer,
        )

        request_func_mock = mocker.patch("urllib3.request")
        request_func_mock.return_value.json.return_value = json.loads("""
{
  "MWT2": {
    "xcache-uc-1": {
      "site": "MWT2",
      "id": "xcache-uc-1",
      "address": "1.1.1.1:1094",
      "size": "34365115224",
      "timestamp": 1759633484503,
      "live": true
    },
    "xcache-uc-2": {
      "site": "MWT2",
      "id": "xcache-uc-2",
      "address": "1.1.1.2:1094",
      "size": "35927165916",
      "timestamp": 1759633466503,
      "live": true
    },
    "xcache-uc-3": {
      "site": "MWT2",
      "id": "xcache-uc-3",
      "address": "1.1.1.3:1094",
      "size": "185222398084",
      "timestamp": 1759633472603,
      "live": true
    }
  }
}""")

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]

            env = container.env
            request_func_mock.assert_called_with("GET", "https://dummy")
            assert _env_value(env, "CACHE_PREFIX") == "root://dummy"

    def test_get_all_deployments(self, mocker, mock_kubernetes):
        mock_api = mock_kubernetes.client.AppsV1Api.return_value
        mock_deployment_list = mocker.MagicMock(name="mock_deployment_list")
        mock_api.list_namespaced_deployment.return_value = mock_deployment_list
        mock_deployment = mocker.MagicMock(name="mock_deployment")
        mock_deployment.metadata.name = "transformer-abc"
        mock_deployment_2 = mocker.MagicMock(name="mock_deployment_2")
        mock_deployment_2.metadata.name = "servicex-internal-abc"
        mock_deployment_list.items = [mock_deployment, mock_deployment_2]

        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=True
        )

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer_manager,
        )

        with client.application.app_context():
            deployments = transformer_manager.get_all_transformer_deployments()
            assert deployments == [mock_deployment]

    def test_get_all_configmaps(self, mocker, mock_kubernetes):
        mock_api = mock_kubernetes.client.CoreV1Api.return_value
        mock_configmap_list = mocker.MagicMock(name="mock_deployment_list")
        mock_api.list_namespaced_config_map.return_value = mock_configmap_list
        mock_configmap = mocker.MagicMock(name="mock_deployment")
        mock_configmap.metadata.name = "abc-generated-source"
        mock_configmap_2 = mocker.MagicMock(name="mock_deployment")
        mock_configmap_2.metadata.name = "servicex-config"
        mock_configmap_list.items = [mock_configmap, mock_configmap_2]

        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=True
        )

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer_manager,
        )

        with client.application.app_context():
            configmaps = transformer_manager.get_all_transformer_configmaps()
            assert configmaps == [mock_configmap]

    def test_get_all_hpas(self, mocker, mock_kubernetes):
        mock_api = mock_kubernetes.client.AutoscalingV1Api.return_value
        mock_hpa_list = mocker.MagicMock(name="mock_deployment_list")
        mock_api.list_namespaced_horizontal_pod_autoscaler.return_value = mock_hpa_list
        mock_hpa = mocker.MagicMock(name="mock_deployment")
        mock_hpa.metadata.name = "transformer-abc"
        mock_hpa_2 = mocker.MagicMock(name="mock_deployment")
        mock_hpa_2.metadata.name = "mysterious_hpa"
        mock_hpa_list.items = [mock_hpa, mock_hpa_2]

        transformer_manager = TransformerManager("external-kubernetes")
        transformer_manager.persistent_volume_claim_exists = mocker.Mock(
            return_value=True
        )

        client = self._test_client(
            extra_config={"TRANSFORMER_AUTOSCALE_ENABLED": False},
            transformation_manager=transformer_manager,
        )

        with client.application.app_context():
            hpas = transformer_manager.get_all_transformer_hpas()
            assert hpas == [mock_hpa]

    def test_launch_transformer_with_pod_scheduling_options(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        node_selector = {"disktype": "ssd", "region": "us-west"}
        tolerations = [
            {
                "key": "dedicated",
                "operator": "Equal",
                "value": "servicex",
                "effect": "NoSchedule",
            },
            {
                "key": "gpu",
                "operator": "Exists",
                "effect": "NoExecute",
                "toleration_seconds": 3600,
            },
        ]
        affinity = {
            "node_affinity": {
                "required_during_scheduling_ignored_during_execution": {
                    "node_selector_terms": [
                        {
                            "match_expressions": [
                                {
                                    "key": "topology.kubernetes.io/zone",
                                    "operator": "In",
                                    "values": ["us-west-1a", "us-west-1b"],
                                }
                            ]
                        }
                    ]
                }
            }
        }
        pod_annotations = {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "8080",
        }

        client = self._test_client(
            extra_config=make_config(
                TRANSFORMER_AUTOSCALE_ENABLED=False,
                TRANSFORMER_NODE_SELECTOR=node_selector,
                TRANSFORMER_TOLERATIONS=tolerations,
                TRANSFORMER_AFFINITY=affinity,
                TRANSFORMER_POD_ANNOTATIONS=pod_annotations,
            ),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_deployment = mock_kubernetes.mock_calls[1][2]["body"]
            template = called_deployment.spec.template

            # Verify pod annotations
            assert template.metadata.annotations == pod_annotations

            # Verify node selector
            assert template.spec.node_selector == node_selector

            # Verify tolerations
            assert len(template.spec.tolerations) == 2
            assert template.spec.tolerations[0].key == "dedicated"
            assert template.spec.tolerations[0].operator == "Equal"
            assert template.spec.tolerations[0].value == "servicex"
            assert template.spec.tolerations[0].effect == "NoSchedule"
            assert template.spec.tolerations[1].key == "gpu"
            assert template.spec.tolerations[1].operator == "Exists"
            assert template.spec.tolerations[1].effect == "NoExecute"
            assert template.spec.tolerations[1].toleration_seconds == 3600

            # Verify affinity
            assert template.spec.affinity is not None
            assert template.spec.affinity.node_affinity is not None

    def test_launch_transformer_with_empty_pod_scheduling_options(self, mocker):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        mock_autoscaling = mocker.Mock()
        mocker.patch.object(
            kubernetes.client, "AutoscalingV1Api", return_value=mock_autoscaling
        )

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        # Test with empty/default values
        client = self._test_client(
            extra_config=make_config(
                TRANSFORMER_AUTOSCALE_ENABLED=False,
                TRANSFORMER_NODE_SELECTOR={},
                TRANSFORMER_TOLERATIONS=[],
                TRANSFORMER_AFFINITY={},
                TRANSFORMER_POD_ANNOTATIONS={},
            ),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="object-store",
                result_format="arrow",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_deployment = mock_kubernetes.mock_calls[1][2]["body"]
            template = called_deployment.spec.template

            # Verify empty values result in None (not empty dicts/lists)
            assert template.metadata.annotations is None
            assert template.spec.node_selector is None
            assert template.spec.tolerations is None
            assert template.spec.affinity is None

    @pytest.mark.parametrize(
        "volume",
        [
            {"hostPath": {"path": "/cvmfs"}},
            {"persistentVolumeClaim": {"claimName": "cvmfs"}},
        ],
    )
    def test_launch_transformer_jobs_with_cvmfs(self, mocker, volume):
        import kubernetes

        mocker.patch.object(kubernetes.config, "load_kube_config")
        mock_kubernetes = mocker.patch.object(kubernetes.client, "AppsV1Api")

        transformer = TransformerManager("external-kubernetes")
        transformer.persistent_volume_claim_exists = mocker.Mock(return_value=True)

        client = self._test_client(
            extra_config=make_config(
                TRANSFORMER_AUTOSCALE_ENABLED=False,
                TRANSFORMER_CVMFS_VOLUME=volume,
            ),
            transformation_manager=transformer,
        )

        with client.application.app_context():
            transformer.launch_transformer_jobs(
                image="sslhep/servicex-transformer:pytest",
                request_id="1234",
                workers=17,
                max_workers=17,
                rabbitmq_uri="ampq://test.com",
                namespace="my-ns",
                result_destination="volume",
                result_format="parquet",
                x509_secret="x509",
                generated_code_cm=None,
                transformer_language="scala",
                transformer_command="echo",
            )
            called_job = mock_kubernetes.mock_calls[1][2]["body"]
            container = called_job.spec.template.spec.containers[0]

            cvmfs_vol = next(
                filter(
                    lambda v: v.name == "cvmfs",
                    called_job.spec.template.spec.volumes,
                )
            )
            # check that one volume type exists
            assert (
                len(
                    [
                        _
                        for _ in cvmfs_vol.to_dict().items()
                        if _[1] is not None and _[0] != "name"
                    ]
                )
                == 1
            )
            # check that all the keys have been snake cased
            for key, subdict in cvmfs_vol.to_dict().items():
                if key == "name":
                    continue
                if subdict is not None:
                    assert all(_.islower() for _ in subdict.keys())

            cvmfs_vol_mount = next(
                filter(lambda m: m.name == "cvmfs", container.volume_mounts)
            )
            assert cvmfs_vol_mount.mount_path == "/cvmfs"


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    # Get the directory where the current file is located
    current_dir = Path(__file__).parent

    os.environ["APP_CONFIG_FILE"] = str(current_dir / "test.config")
    app = servicex_app.create_app()
    app.config["TESTING"] = True
    # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app


@pytest.fixture
def app_context(app):
    """Create an application context."""
    with app.app_context():
        yield app


class TestShutdownPod:
    def _make_req(self, status):
        req = TransformRequest()
        req.request_id = "test-123"
        req.status = status
        return req

    def test_skips_shutdown_for_terminal_status(self, app_context, mocker):
        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        req = self._make_req(TransformStatus.complete)
        manager.cancel_transform(req)
        manager.shutdown_transformer_job.assert_not_called()

    def test_calls_shutdown_for_pending_lookup(self, app_context, mocker):
        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        req = self._make_req(TransformStatus.pending_lookup)
        manager.cancel_transform(req)
        manager.shutdown_transformer_job.assert_called_once_with("test-123", "test-ns")

    def test_calls_shutdown_for_running(self, app_context, mocker):
        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        req = self._make_req(TransformStatus.running)
        manager.cancel_transform(req)
        manager.shutdown_transformer_job.assert_called_once_with("test-123", "test-ns")

    def test_calls_shutdown_for_lookup(self, app_context, mocker):
        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        req = self._make_req(TransformStatus.lookup)
        manager.cancel_transform(req)
        manager.shutdown_transformer_job.assert_called_once_with("test-123", "test-ns")

    def test_404_swallowed(self, app_context, mocker):
        import kubernetes

        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        manager.shutdown_transformer_job.side_effect = (
            kubernetes.client.exceptions.ApiException(status=404)
        )
        req = self._make_req(TransformStatus.running)
        manager.cancel_transform(req)

    def test_non_404_logs_and_reraises(self, app_context, mocker):
        import kubernetes

        app_context.config["TRANSFORMER_NAMESPACE"] = "test-ns"

        mocker.patch(
            "servicex_app.transformer_manager.kubernetes.config.load_incluster_config"
        )
        manager = TransformerManager("internal-kubernetes")
        manager.shutdown_transformer_job = Mock()
        mock_error = mocker.patch.object(app_context.logger, "error")
        manager.shutdown_transformer_job.side_effect = (
            kubernetes.client.exceptions.ApiException(status=403, reason="Forbidden")
        )
        with pytest.raises(kubernetes.client.exceptions.ApiException):
            req = self._make_req(TransformStatus.running)
            manager.cancel_transform(req)
        mock_error.assert_called_once()
