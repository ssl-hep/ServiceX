from flask import Response, url_for

from .web_test_base import WebTestBase


class TestAuthCallback(WebTestBase):
    module = "servicex_app.web.auth_callback"

    def test_auth_callback_outgoing(self, client, oauth_client):
        response: Response = client.get(url_for("auth_callback"))
        assert response.status_code == 302
        assert oauth_client.authorize_redirect.called_once()
        assert response.location == self._auth_url()

    def test_auth_callback_incoming_new(
        self, client, oauth_client, mock_session, mocker
    ):
        response: Response = client.get(
            url_for("auth_callback"), query_string={"code": "oauth-code"}
        )
        assert oauth_client.authorize_access_token.called_once()
        id_token = self._id_token()
        assert mock_session.get("is_authenticated")
        assert mock_session.get("name") == id_token["name"]
        assert mock_session.get("sub") == id_token["sub"]
        assert response.status_code == 302
        assert response.location == url_for("create_profile")

    def test_auth_callback_incoming_existing(
        self, client, oauth_client, user, mock_session, mocker
    ):
        response: Response = client.get(
            url_for("auth_callback"), query_string={"code": "oauth-code"}
        )
        assert oauth_client.authorize_access_token.called_once()
        id_token = self._id_token()
        assert mock_session.get("user_id") == user.id
        assert mock_session.get("admin") == user.admin
        assert mock_session.get("is_authenticated")
        assert mock_session.get("name") == id_token["name"]
        assert mock_session.get("sub") == id_token["sub"]
        assert response.status_code == 302
        assert response.location == url_for("user-dashboard")
