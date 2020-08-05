from urllib.parse import quote
from functools import reduce

from flask import Response, url_for, session

from .web_test_base import WebTestBase


class TestAuthCallback(WebTestBase):
    def test_auth_callback_outgoing(self, client, globus_client):
        response: Response = client.get(url_for('auth_callback'))
        assert response.status_code == 302
        assert globus_client.oauth2_start_flow.called_once()
        assert globus_client.oauth2_get_authorize_url.called_once()
        assert response.location == self._auth_url()

    def test_auth_callback_incoming_new(self, client, globus_client):
        response: Response = client.get(url_for('auth_callback'),
                                        query_string={'code': 'oauth-code'})
        assert globus_client.oauth2_exchange_code_for_tokens\
            .called_once_with('oauth-code')
        id_token = self._id_token()
        assert session.get('is_authenticated')
        assert session.get('name') == id_token['name']
        assert session.get('sub') == id_token['sub']
        assert response.status_code == 302
        assert response.location == url_for('create_profile', _external=True)

    def test_auth_callback_incoming_existing(self, client, globus_client, user):
        response: Response = client.get(url_for('auth_callback'),
                                        query_string={'code': 'oauth-code'})
        assert globus_client.oauth2_exchange_code_for_tokens\
            .called_once_with('oauth-code')
        id_token = self._id_token()
        assert session.get('user_id') == user.id
        assert session.get('admin') == user.admin
        assert session.get('is_authenticated')
        assert session.get('name') == id_token['name']
        assert session.get('sub') == id_token['sub']
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)
