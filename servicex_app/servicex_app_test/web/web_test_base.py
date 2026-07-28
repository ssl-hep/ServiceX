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
from datetime import datetime
from unittest.mock import MagicMock

from flask import template_rendered, redirect
from flask.testing import FlaskClient
from flask_jwt_extended import create_access_token
from pytest import fixture


class WebTestBase:
    module = ""

    @staticmethod
    def fake_header():
        access_token = create_access_token("testuser")
        headers = {"Authorization": "Bearer {}".format(access_token)}
        return headers

    @staticmethod
    def _app_config():
        return {
            "TESTING": True,
            "SECRET_KEY": "secret",
            "WTF_CSRF_ENABLED": False,
            "RABBIT_MQ_URL": "amqp://foo.com",
            "RABBIT_RETRIES": 12,
            "RABBIT_RETRY_INTERVAL": 10,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TRANSFORMER_RABBIT_MQ_URL": "amqp://trans.rabbit",
            "TRANSFORMER_NAMESPACE": "my-ws",
            "TRANSFORMER_MANAGER_ENABLED": False,
            "TRANSFORMER_MANAGER_MODE": "external",
            "TRANSFORMER_MAX_REPLICAS": 5,
            "ADVERTISED_HOSTNAME": "cern.analysis.ch:5000",
            "TRANSFORMER_PULL_POLICY": "Always",
            "OBJECT_STORE_ENABLED": False,
            "MINIO_URL": "localhost:9000",
            "MINIO_ACCESS_KEY": "miniouser",
            "MINIO_SECRET_KEY": "leftfoot1",
            "CODE_GEN_SERVICE_URL": "http://localhost:5001",
            "CODE_GEN_SERVICE_URLS": {
                "atlasxaod": "http://servicex-code-gen-atlasxaod:8000",
                "cms": "http://servicex-code-gen-cms:8000",
                "python": "http://servicex-code-gen-python:8000",
                "uproot": "http://servicex-code-gen-uproot:8000",
            },
            "CODE_GEN_IMAGES": {
                "atlasxaod": "sslhep/servicex_code_gen_func_adl_xaod:develop",
                "cms": "sslhep/servicex_code_gen_cms_aod:develop",
                "python": "sslhep/servicex_code_gen_python:develop",
                "uproot": "sslhep/servicex_code_gen_func_adl_uproot:develop",
            },
            "ENABLE_AUTH": False,
            "OAUTH_METADATA_URL": "https://auth.globus.org/.well-known/openid-configuration",
            "OAUTH_CLIENT_ID": "globus-client-id",
            "OAUTH_CLIENT_SECRET": "globus-client-secret",
            "DID_FINDER_DEFAULT_SCHEME": "rucio",
            "VALID_DID_SCHEMES": ["rucio"],
            "JWT_ADMIN": "admin",
            "JWT_PASS": "pass",
            "JWT_SECRET_KEY": "schtum",
            "DID_RUCIO_FINDER_TAG": "develop",
            "DID_CERNOPENDATA_FINDER_TAG": "develop",
            "APP_IMAGE_TAG": "develop",
            "LOGS_URL": "http://kibana.example.com",
        }

    @staticmethod
    def _test_client(extra_config=None) -> FlaskClient:
        from servicex_app import create_app

        config = WebTestBase._app_config()
        if extra_config:
            config.update(extra_config)
        app = create_app(config)
        app.test_request_context().push()
        return app.test_client()

    @staticmethod
    def _test_user():
        from servicex_app.models import UserModel

        return UserModel(
            name="Jane Doe",
            email="jane@example.com",
            sub="janedoe",
            institution="UChicago",
            experiment="ATLAS",
            refresh_token="abcdef",
        )

    @staticmethod
    def _auth_url():
        return "http://www.example.com"

    @staticmethod
    def _oauth_tokens():
        return {"access_token": "opaque", "id_token": "opaque"}

    @staticmethod
    def _globus_metadata():
        return {
            "request_token_url": None,
            "request_token_params": None,
            "refresh_token_url": None,
            "refresh_token_params": None,
            "issuer": "https://auth.globus.org",
            "authorization_endpoint": "https://auth.globus.org/v2/oauth2/authorize",
            "userinfo_endpoint": "https://auth.globus.org/v2/oauth2/userinfo",
            "token_endpoint": "https://auth.globus.org/v2/oauth2/token",
            "revocation_endpoint": "https://auth.globus.org/v2/oauth2/token/revoke",
            # the following is not actually returned for Globus, but we use for testing
            "end_session_endpoint": "https://auth.globus.org/v2/web/logout",
            "jwks_uri": "https://auth.globus.org/jwk.json",
            "response_types_supported": ["code", "token", "token id_token", "id_token"],
            "id_token_signing_alg_values_supported": ["RS512"],
            "scopes_supported": ["openid", "email", "profile"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "claims_supported": [
                "at_hash",
                "aud",
                "email",
                "exp",
                "name",
                "nonce",
                "preferred_username",
                "iat",
                "iss",
                "sub",
            ],
            "subject_types_supported": ["public"],
            "_loaded_at": 1740439075.4229648,
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
                    "sub": "primary-oauth-id",
                },
                {
                    "email": "jane@uchicago.edu",
                    "identity_provider_display_name": "Google",
                    "last_authentication": 1595552908,
                    "identity_provider": "secondary-oauth-id",
                    "username": "jane@uchicago.edu@accounts.google.com",
                    "name": "Jane Doe",
                    "sub": "secondary-oauth-id",
                },
            ],
            "name": "Jane Doe",
            "aud": "application-audience-id",
            "iat": 1595955388,
            "sub": "primary-oauth-id",
        }

    @staticmethod
    def _test_transformation_req(**kwargs):
        from servicex_app.models import TransformRequest

        defaults = {
            "id": 1234,
            "did": "foo",
            "request_id": "b5901cca-9858-42e7-a093-0929cf391f0e",
            "submit_time": datetime.utcnow(),
            "code_gen_image": "someimage:dev",
        }
        defaults.update(kwargs)
        return TransformRequest(**defaults)

    @fixture
    def client(self):
        return self._test_client()

    @fixture
    def captured_templates(self, client):
        # Based on https://stackoverflow.com/a/58204843/8534196
        recorded = []

        def record(sender, template, context, **extra):
            recorded.append((template, context))

        template_rendered.connect(record, client.application)
        try:
            yield recorded
        finally:
            template_rendered.disconnect(record, client.application)

    @fixture
    def user(self, mocker):
        user = self._test_user()
        user.save_to_db = mocker.Mock()
        user.delete_from_db = mocker.Mock()
        mocker.patch("servicex_app.models.UserModel.find_by_sub", return_value=user)
        mocker.patch("servicex_app.models.UserModel.find_by_email", return_value=user)
        mocker.patch("servicex_app.models.UserModel.find_by_id", return_value=user)
        return user

    @fixture
    def db(self, mocker):
        mock_db = MagicMock()
        mock_db.session = MagicMock()
        mock_db.session.commit = MagicMock()
        return mock_db

    @fixture
    def oauth_client(self, mocker):
        client_cls = mocker.patch("authlib.integrations.flask_client.FlaskOAuth2App")
        client = client_cls.return_value
        auth_url = self._auth_url()
        client.authorize_redirect = mocker.Mock(return_value=redirect(auth_url))
        tokens = self._oauth_tokens()
        tokens["userinfo"] = self._id_token()
        client.authorize_access_token = mocker.Mock(return_value=tokens)
        client.server_metadata = self._globus_metadata()
        from authlib.integrations.flask_client import OAuth

        mocker.patch.object(OAuth, "oauth2_client_cls", client_cls)

        yield client

    @fixture
    def oauth_session(self, mocker):
        session_cls = mocker.patch("authlib.integrations.requests_client.OAuth2Session")
        session = session_cls.return_value
        session.revoke_token = mocker.MagicMock()

        return session

    @fixture
    def mock_session(self, mocker):
        if not self.module:
            raise ValueError("Please provide a module name!")
        return mocker.patch(f"{self.module}.session", dict())

    @fixture
    def mock_flash(self, mocker):
        if not self.module:
            raise ValueError("Please provide a module name!")
        return mocker.patch(f"{self.module}.flash", mocker.MagicMock(name="mock_flash"))
