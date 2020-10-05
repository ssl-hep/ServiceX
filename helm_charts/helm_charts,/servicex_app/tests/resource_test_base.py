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
from pytest import fixture

from servicex import create_app
from servicex.models import TransformRequest
from servicex.rabbit_adaptor import RabbitAdaptor
from servicex.code_gen_adapter import CodeGenAdapter
from servicex.docker_repo_adapter import DockerRepoAdapter


class ResourceTestBase:

    @staticmethod
    def _app_config():
        return {
            'TESTING': True,
            'RABBIT_MQ_URL': 'amqp://foo.com',
            'RABBIT_RETRIES': 12,
            'RABBIT_RETRY_INTERVAL': 10,
            'SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TRANSFORMER_RABBIT_MQ_URL': "amqp://trans.rabbit",
            'TRANSFORMER_NAMESPACE': "my-ws",
            'TRANSFORMER_MANAGER_ENABLED': False,
            'TRANSFORMER_AUTOSCALE_ENABLED': True,
            'ADVERTISED_HOSTNAME': 'cern.analysis.ch:5000',
            'TRANSFORMER_PULL_POLICY': 'Always',
            'TRANSFORMER_VALIDATE_DOCKER_IMAGE': True,
            'OBJECT_STORE_ENABLED': False,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1',
            'CODE_GEN_SERVICE_URL': 'http://localhost:5001',
            'ENABLE_AUTH': False,
            'JWT_ADMIN': 'admin@example.com',
            'JWT_PASS': 'pass',
            'JWT_SECRET_KEY': 'schtum',
            'TRANSFORMER_DEFAULT_IMAGE': "sslhep/servicex_func_adl_xaod_transformer:1.0.0-RC.3",
            'CODE_GEN_IMAGE': "sslhep/servicex_code_gen_func_adl_xaod:develop"
        }

    @staticmethod
    def _test_client(extra_config=None,
                     transformation_manager=None,
                     rabbit_adaptor=None,
                     object_store=None,
                     elasticsearch_adapter=None,
                     code_gen_service=None,
                     lookup_result_processor=None,
                     docker_repo_adapter=None):
        config = ResourceTestBase._app_config()
        config['TRANSFORMER_MANAGER_ENABLED'] = False
        config['TRANSFORMER_MANAGER_MODE'] = 'external'

        if extra_config:
            config.update(extra_config)

        app = create_app(config, transformation_manager, rabbit_adaptor,
                         object_store, elasticsearch_adapter, code_gen_service,
                         lookup_result_processor, docker_repo_adapter)

        return app.test_client()

    @staticmethod
    def _generate_transform_request():
        transform_request = TransformRequest()
        transform_request.submit_time = 1000
        transform_request.request_id = 'BR549'
        transform_request.columns = 'electron.eta(), muon.pt()'
        transform_request.tree_name = 'Events'
        transform_request.chunk_size = 1000
        transform_request.workers = 42
        transform_request.did = '123-456-789'
        transform_request.image = 'ssl-hep/foo:latest'
        transform_request.result_destination = 'kafka'
        transform_request.result_format = 'arrow'
        transform_request.kafka_broker = 'http://ssl-hep.org.kafka:12345'
        transform_request.total_events = 10000
        transform_request.total_bytes = 1203
        transform_request.status = "Submitted"
        transform_request.app_version = '1.0.1'
        transform_request.code_gen_image = "sslhep/servicex_code_gen_func_adl_xaod:develop"
        return transform_request

    @fixture
    def mock_rabbit_adaptor(self, mocker):
        return mocker.MagicMock(RabbitAdaptor)

    @fixture
    def mock_code_gen_service(self, mocker):
        return mocker.MagicMock(CodeGenAdapter)

    @fixture
    def mock_docker_repo_adapter(self, mocker):
        docker = mocker.MagicMock(DockerRepoAdapter)
        docker.check_image_exists = mocker.Mock(return_value=True)
        return docker

    @fixture
    def mock_jwt_required(self, mocker):
        def identity(fn):
            return fn
        mocker.patch('servicex.decorators.jwt_required', side_effect=identity)

    @fixture
    def mock_requesting_user(self, mocker):
        test_id = 6
        mock_user = mocker.Mock()
        mock_user.id = test_id
        mock_user.admin = False
        mock_user.pending = False
        mocker.patch(
            'servicex.resources.servicex_resource.UserModel.find_by_sub',
            return_value=mock_user)
        return mock_user

    @fixture
    def mock_app_version(self, mocker):
        from servicex.resources.servicex_resource import ServiceXResource
        mocker.patch.object(ServiceXResource,
                            "_get_app_version",
                            return_value='3.14.15')
