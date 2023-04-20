from flask import Response, url_for

from .web_test_base import WebTestBase


class TestAuthCallback(WebTestBase):
    module = "servicex.web.auth_callback"

    def test_auth_callback_outgoing(self, globus_client):
        client = self._test_client(extra_config={
            'ENABLE_AUTH': True,
            'JWT_ISSUER': "globus"})

        response: Response = client.get(url_for('auth_callback'))
        assert response.status_code == 302
        assert globus_client.oauth2_start_flow.called_once()
        assert globus_client.oauth2_get_authorize_url.called_once()
        assert response.location == self._auth_url()

    def test_auth_callback_incoming_new(self, globus_client, mock_session, mocker):
        client = self._test_client(extra_config={
            'ENABLE_AUTH': True,
            'JWT_ISSUER': "globus"})

        mocker.patch('servicex.web.auth_callback.AccessTokenAuthorizer')
        auth_client_cls = mocker.patch('servicex.web.auth_callback.AuthClient')
        auth_client = auth_client_cls.return_value
        id_token = self._id_token()

        auth_client.oauth2_userinfo.return_value = id_token

        response: Response = client.get(url_for('auth_callback'),
                                        query_string={'code': 'oauth-code'})
        assert globus_client.oauth2_exchange_code_for_tokens\
            .called_once_with('oauth-code')

        assert mock_session.get('is_authenticated')
        assert mock_session.get('name') == id_token['name']
        assert mock_session.get('sub') == id_token['sub']
        assert response.status_code == 302
        assert response.location == url_for('create_profile')

    def test_auth_callback_incoming_existing(
            self, globus_client, user, mock_session, mocker
    ):
        client = self._test_client(extra_config={
            'ENABLE_AUTH': True,
            'JWT_ISSUER': "globus"})

        mocker.patch('servicex.web.auth_callback.AccessTokenAuthorizer')

        auth_client_cls = mocker.patch('servicex.web.auth_callback.AuthClient')
        auth_client = auth_client_cls.return_value
        id_token = self._id_token()

        auth_client.oauth2_userinfo.return_value = id_token

        response: Response = client.get(url_for('auth_callback'),
                                        query_string={'code': 'oauth-code'})
        assert globus_client.oauth2_exchange_code_for_tokens\
            .called_once_with('oauth-code')
        id_token = self._id_token()
        assert mock_session.get('user_id') == user.id
        assert mock_session.get('admin') == user.admin
        assert mock_session.get('is_authenticated')
        assert mock_session.get('name') == id_token['name']
        assert mock_session.get('sub') == id_token['sub']
        assert response.status_code == 302
        assert response.location == url_for('user-dashboard')
