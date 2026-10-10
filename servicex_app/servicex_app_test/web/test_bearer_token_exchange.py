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
from servicex_app_test.resource_test_base import ResourceTestBase


class TestBearerTokenExchange(ResourceTestBase):
    def test_device_flow_info_notconfigured(self, client):
        response = client.get("/device-flow-info")
        assert response.status_code == 404

    def test_device_flow_info_configured(self):
        client = self._test_client(
            extra_config={
                "OAUTH_DEVICE_FLOW_CLIENT_ID": "oidc",
                "OAUTH_METADATA_URL": "https://auth.site/.conf",
            }
        )
        response = client.get("/device-flow-info")
        assert response.status_code == 200
        print(response.json)
        assert response.json == {
            "client": "oidc",
            "config": "https://auth.site/.conf",
        }

    def test_bearer_token_exchange(self, requests_mock, mocker):
        mocker.patch(
            "servicex_app.resources.users.bearer_token_exchange.create_refresh_token",
            return_value="Qaaaa",
        )
        client = self._test_client(
            extra_config={
                "OAUTH_DEVICE_FLOW_CLIENT_ID": "oidc",
                "OAUTH_METADATA_URL": "https://auth.site/.conf",
                "OAUTH_CLIENT_ID": "oidc-secret",
                "OAUTH_CLIENT_SECRET": "secret",
            }
        )

        requests_mock.get(
            "https://auth.site/.conf",
            json={"userinfo_endpoint": "https://auth.site/userinfo"},
        )
        requests_mock.get(
            "https://auth.site/userinfo",
            json={"email": "user@fancy.place", "sub": "unique"},
        )

        # Path without automatic user acceptance
        auth_header = {"Authorization": "Bearer xxx"}
        response = client.get("/bearer-token-exchange", headers=auth_header)
        assert response.status_code == 200
        assert response.json == {"jwt": "Qaaaa", "pending": True}

        # Path with automatic user acceptance
        client = self._test_client(
            extra_config={
                "OAUTH_DEVICE_FLOW_CLIENT_ID": "oidc",
                "OAUTH_METADATA_URL": "https://auth.site/.conf",
                "OAUTH_CLIENT_ID": "oidc-secret",
                "OAUTH_CLIENT_SECRET": "secret",
                "OAUTH_ALLOW_ALL_AFTER_AUTH": True,
            }
        )
        response = client.get("/bearer-token-exchange", headers=auth_header)
        assert response.status_code == 200
        assert response.json == {"jwt": "Qaaaa", "pending": False}

        # Weird Globus path
        requests_mock.get(
            "https://auth.site/userinfo",
            json={"identity_set": [{"email": "user@fancy.place"}], "sub": "unique"},
        )
        response = client.get("/bearer-token-exchange", headers=auth_header)
        assert response.status_code == 200
        assert response.json == {"jwt": "Qaaaa", "pending": False}

        # Path with existing user
        user_class = mocker.patch(
            "servicex_app.resources.users.bearer_token_exchange.UserModel.find_by_email"
        )
        user_instance = user_class.return_value
        user_instance.id = 1
        user_instance.name = "Jane Doe"
        user_instance.admin = False
        user_instance.pending = False
        user_instance.refresh_token = "Naaaa"
        response = client.get("/bearer-token-exchange", headers=auth_header)
        assert response.status_code == 200
        assert response.json == {"jwt": "Naaaa", "pending": False}

    def test_bearer_token_exchange_fails(self, requests_mock, mocker):
        mocker.patch(
            "servicex_app.resources.users.bearer_token_exchange.create_refresh_token",
            return_value="Qaaaa",
        )
        client = self._test_client(
            extra_config={
                "OAUTH_DEVICE_FLOW_CLIENT_ID": "oidc",
                "OAUTH_METADATA_URL": "https://auth.site/.conf",
                "OAUTH_CLIENT_ID": "oidc-secret",
                "OAUTH_CLIENT_SECRET": "secret",
            }
        )

        # call with no token will fail
        response = client.get("/bearer-token-exchange")
        assert response.status_code == 403

        # fails if we can't determine email
        requests_mock.get(
            "https://auth.site/.conf",
            json={"userinfo_endpoint": "https://auth.site/userinfo"},
        )
        requests_mock.get(
            "https://auth.site/userinfo", json={"email": "", "sub": "unique"}
        )
        auth_header = {"Authorization": "Bearer xxx"}
        response = client.get("/bearer-token-exchange", headers=auth_header)
        assert response.status_code == 403
