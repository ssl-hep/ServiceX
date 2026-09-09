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
from flask import Response
from pytest import fixture
from servicex_app_test.resource_test_base import ResourceTestBase


class TestAllTransformationRequest(ResourceTestBase):
    @staticmethod
    def example_json():
        return [{"request_id": "123"}, {"request_id": "456"}]

    @fixture()
    def mock_return_json(self, mocker):
        import servicex_app

        mock_return_json = mocker.patch.object(
            servicex_app.models.TransformRequest,
            "return_json",
            return_value=self.example_json(),
        )
        return mock_return_json

    def test_get_all_auth_disabled(self, client, mock_return_json):
        response: Response = client.get("/servicex/transformation")
        assert response.status_code == 200
        assert response.json == self.example_json()
        mock_return_json.assert_called()

    @fixture()
    def mock_query(self, mocker):
        mock_tr_cls = mocker.patch(
            "servicex_app.resources.transformation.get_all.TransformRequest"
        )
        mock_tr_cls.return_json.return_value = self.example_json()
        return mock_tr_cls.query

    def test_get_all_auth_enabled(
        self, mock_jwt_extended, mock_requesting_user, mock_query
    ):
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                "/servicex/transformation", headers=self.fake_header()
            )
        assert response.status_code == 200
        assert response.json == self.example_json()
        # A non-admin user only sees their own requests
        mock_query.filter_by.assert_called_once_with(
            submitted_by=mock_requesting_user.id
        )
        mock_query.all.assert_not_called()

    def test_get_all_as_admin(
        self, mock_jwt_extended, mock_requesting_user, mock_query
    ):
        mock_requesting_user.admin = True
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                "/servicex/transformation", headers=self.fake_header()
            )
        assert response.status_code == 200
        assert response.json == self.example_json()
        mock_query.all.assert_called_once_with()

    def test_get_by_user(self, mock_jwt_extended, mock_requesting_user, mock_query):
        user_id = mock_requesting_user.id
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                f"/servicex/transformation?submitted_by={user_id}",
                headers=self.fake_header(),
            )
        assert response.status_code == 200
        assert response.json == self.example_json()
        mock_query.filter_by.assert_called_once_with(submitted_by=user_id)

    def test_get_by_other_user_forbidden(
        self, mock_jwt_extended, mock_requesting_user, mock_query
    ):
        other_id = mock_requesting_user.id + 1
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                f"/servicex/transformation?submitted_by={other_id}",
                headers=self.fake_header(),
            )
        assert response.status_code == 403
        mock_query.filter_by.assert_not_called()
        mock_query.all.assert_not_called()

    def test_get_by_other_user_as_admin(
        self, mock_jwt_extended, mock_requesting_user, mock_query
    ):
        mock_requesting_user.admin = True
        other_id = mock_requesting_user.id + 1
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                f"/servicex/transformation?submitted_by={other_id}",
                headers=self.fake_header(),
            )
        assert response.status_code == 200
        mock_query.filter_by.assert_called_once_with(submitted_by=other_id)

    def test_get_by_user_zero(
        self, mock_jwt_extended, mock_requesting_user, mock_query
    ):
        """submitted_by=0 must not be treated as an absent filter."""
        mock_requesting_user.admin = True
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.application.app_context():
            response = client.get(
                "/servicex/transformation?submitted_by=0",
                headers=self.fake_header(),
            )
        assert response.status_code == 200
        mock_query.filter_by.assert_called_once_with(submitted_by=0)
        mock_query.all.assert_not_called()
