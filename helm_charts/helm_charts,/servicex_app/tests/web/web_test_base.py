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
from servicex.models import UserModel
from servicex.rabbit_adaptor import RabbitAdaptor


class WebTestBase:
    @staticmethod
    def _app_config():
        return {
            'TESTING': True,
            'SECRET_KEY': 'secret',
            'WTF_CSRF_ENABLED': False,
            'RABBIT_MQ_URL': 'amqp://foo.com',
            'RABBIT_RETRIES': 12,
            'RABBIT_RETRY_INTERVAL': 10,
            'SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TRANSFORMER_RABBIT_MQ_URL': "amqp://trans.rabbit",
            'TRANSFORMER_NAMESPACE': "my-ws",
            'TRANSFORMER_MANAGER_ENABLED': False,
            'TRANSFORMER_MANAGER_MODE': 'external',
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
            'JWT_SECRET_KEY': 'schtum',
        }

    @staticmethod
    def _test_client(mocker, extra_config=None):
        config = WebTestBase._app_config()
        if extra_config:
            config.update(extra_config)
        mock_rabbit_adaptor = mocker.MagicMock(RabbitAdaptor)
        app = create_app(config, provided_rabbit_adaptor=mock_rabbit_adaptor)
        app.test_request_context().push()
        return app.test_client()

    @staticmethod
    def _test_user():
        return UserModel(
            name='Jane Doe',
            email='jane@example.com',
            sub='janedoe',
            institution='UChicago',
            experiment='ATLAS')

    @staticmethod
    def _auth_url():
        return 'http://www.example.com'

    @staticmethod
    def _oauth_tokens():
        return {
            'auth.globus.org': {
                'access_token': 'globus-auth-access-token',
                'expires_at_seconds': 1596734412,
                'refresh_token': 'globus-auth-refresh-token',
                'resource_server': 'auth.globus.org',
                'scope': 'email profile openid',
                'token_type': 'Bearer'},
            'transfer.api.globus.org': {
                'access_token': 'globus-transfer-access-token',
                'expires_at_seconds': 1596734412,
                'refresh_token': 'globus-transfer-refresh-token',
                'resource_server': 'transfer.api.globus.org',
                'scope': 'urn:globus:auth:scope:transfer.api.globus.org:all',
                'token_type': 'Bearer'}
        }

    @staticmethod
    def _id_token():
        return {
            "iss": "https://auth.globus.org",
            "exp": 1596128188,
            "identity_provider": "primary-identity-provider-id",
            "organization": "CERN",
            "at_hash": "at-hash",
            "email": "jane@cern.ch",
            "preferred_username": "jane@cern.ch",
            "identity_provider_display_name": "CERN",
            "last_authentication": 1595620302,
            "identity_set": [
                {
                  "email": "jane@cern.ch",
                  "identity_provider_display_name": "CERN",
                  "identity_provider": "primary-identity-provider-id",
                  "organization": "CERN",
                  "username": "jane@cern.ch",
                  "name": "Jane Doe",
                  "last_authentication": 1595620302,
                  "sub": "primary-oauth-id"
                },
                {
                  "email": "jane@uchicago.edu",
                  "identity_provider_display_name": "Google",
                  "last_authentication": 1595552908,
                  "identity_provider": "secondary-oauth-id",
                  "username": "jane@uchicago.edu@accounts.google.com",
                  "name": "Jane Doe",
                  "sub": "secondary-oauth-id"
                }
            ],
            "name": "Jane Doe",
            "aud": "application-audience-id",
            "iat": 1595955388,
            "sub": "primary-oauth-id"
        }

    @fixture
    def client(self, mocker):
        with self._test_client(mocker) as client:
            yield client

    @fixture
    def user(self, mocker):
        user = self._test_user()
        mocker.patch('servicex.models.UserModel.find_by_sub', return_value=user)
        return user

    @fixture
    def new_user(self, mocker):
        return mocker.patch('servicex.models.UserModel').return_value

    @fixture
    def db(self, mocker):
        return mocker.patch('flask_sqlalchemy.SQLAlchemy').return_value

    @fixture
    def globus_client(self, mocker):
        client_cls = mocker.patch('globus_sdk.ConfidentialAppAuthClient')
        client = client_cls.return_value
        auth_url = self._auth_url()
        client.oauth2_get_authorize_url = mocker.Mock(return_value=auth_url)
        mock_oauth_tokens = mocker.Mock()
        mock_oauth_tokens.decode_id_token = \
            mocker.MagicMock(return_value=self._id_token())
        mock_oauth_tokens.by_resource_server = self._oauth_tokens()
        client.oauth2_exchange_code_for_tokens = \
            mocker.Mock(return_value=mock_oauth_tokens)
        mock_intro = mocker.Mock()
        mock_intro.data = {'identity_set': ['primary-oauth-id',
                                            'secondary-oauth-id']}
        client.oauth2_token_introspect = mocker.Mock(return_value=mock_intro)
        return client
