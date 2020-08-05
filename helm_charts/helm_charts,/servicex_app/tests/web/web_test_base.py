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
from servicex.rabbit_adaptor import RabbitAdaptor


class WebTestBase:

    @staticmethod
    def _app_config():
        return {
            'TESTING': True,
            'SECRET_KEY': 'secret',
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
            'OBJECT_STORE_ENABLED': False,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1',
            'CODE_GEN_SERVICE_URL': 'http://localhost:5001',
            'ENABLE_AUTH': False,
            'GLOBUS_CLIENT_ID': 'globus-client-id',
            'GLOBUS_CLIENT_SECRET': 'globus-client-secret',
            'JWT_ADMIN': 'admin',
            'JWT_PASS': 'pass',
            'JWT_SECRET_KEY': 'schtum'
        }

    @staticmethod
    def _test_client(additional_config=None,
                     transformation_manager=None,
                     rabbit_adaptor=None,
                     object_store=None,
                     elasticsearch_adapter=None,
                     code_gen_service=None,
                     lookup_result_processor=None):
        config = WebTestBase._app_config()
        config['TRANSFORMER_MANAGER_ENABLED'] = False
        config['TRANSFORMER_MANAGER_MODE'] = 'external'

        if additional_config:
            config.update(additional_config)

        app = create_app(config, transformation_manager, rabbit_adaptor,
                         object_store, elasticsearch_adapter, code_gen_service,
                         lookup_result_processor)

        return app.test_client()

    @fixture
    def client(self, mocker):
        config = WebTestBase._app_config()
        config['TRANSFORMER_MANAGER_ENABLED'] = False
        config['TRANSFORMER_MANAGER_MODE'] = 'external'
        rabbit_adaptor = mocker.MagicMock(RabbitAdaptor)
        app = create_app(config, provided_rabbit_adaptor=rabbit_adaptor)
        app.test_request_context().push()
        with app.test_client() as client:
            yield client

    # @staticmethod
    # def mock_session(mocker, some_dict):
    #     mock = mocker.MagicMock()
    #     mock.__getitem__.side_effect = lambda name: some_dict[name]
    #     return mock

    # @fixture
    # def mock_rabbit_adaptor(self, mocker):
    #     return mocker.MagicMock(RabbitAdaptor)

