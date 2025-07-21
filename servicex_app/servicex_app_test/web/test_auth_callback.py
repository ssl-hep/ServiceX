from flask import Response, url_for
from .web_test_base import WebTestBase


class TestAuthCallback(WebTestBase):
    module = "servicex_app.web.auth_callback"
    userinfo = {
            "id_token": {
            },
            "userinfo": {
                "email": "<EMAIL>",
                "name": "Jane Doe",
                "sub": "primary-oauth-id",
                "preferred_username": "testuser",
                "organization": "Test Organization"

            },
            "access_token": ""
    }

    def test_auth_callback_outgoing(self, client, oauth_client):
        response: Response = client.get(url_for("auth_callback"))
        assert response.status_code == 302
        oauth_client.authorize_redirect.assert_called_once()
        assert response.location == self._auth_url()

    def test_auth_callback_incoming_new(
        self, client, oauth_client, mock_session, mocker
    ):
        mock_user_model = mocker.patch("servicex_app.web.auth_callback.UserModel")
        mock_user_model.find_by_email.return_value = None  # User does not exist

        mock_oauth = mocker.patch("servicex_app.web.auth_callback.load_oauth_client").return_value
        mock_oauth.oauth = mocker.Mock()
        mock_oauth.oauth.authorize_access_token = mocker.Mock(return_value=self.userinfo)

        response: Response = client.get(
            url_for("auth_callback"), query_string={"code": "oauth-code"}
        )
        mock_oauth.authorize_redirect.assert_not_called()
        mock_user_model.find_by_email.assert_called_once()
        id_token = self._id_token()
        assert mock_session.get("is_authenticated")
        assert mock_session.get("name") == id_token["name"]
        assert mock_session.get("sub") == id_token["sub"]
        assert response.status_code == 302
        assert response.location == url_for("create_profile")

    def test_auth_callback_incoming_existing(
        self, client, oauth_client, user, mock_session, mocker
    ):
        mock_user_model = mocker.patch("servicex_app.web.auth_callback.UserModel")
        mock_user_model.find_by_email.return_value = user  # User does exist

        mock_oauth = mocker.patch("servicex_app.web.auth_callback.load_oauth_client").return_value
        mock_oauth.oauth = mocker.Mock()
        mock_oauth.oauth.authorize_access_token = mocker.Mock(return_value=self.userinfo)

        response: Response = client.get(
            url_for("auth_callback"), query_string={"code": "oauth-code"}
        )
        mock_oauth.oauth.authorize_access_token.assert_called_once()
        id_token = self._id_token()
        assert mock_session.get("user_id") == user.id
        assert mock_session.get("admin") == user.admin
        assert mock_session.get("is_authenticated")
        assert mock_session.get("name") == id_token["name"]
        assert mock_session.get("sub") == id_token["sub"]
        assert response.status_code == 302
        assert response.location == url_for("user-dashboard")
