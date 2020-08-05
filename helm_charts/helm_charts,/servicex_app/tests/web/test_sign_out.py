from urllib.parse import quote
from functools import reduce

from flask import Response, url_for, session

from .web_test_base import WebTestBase

dummy_tokens = {
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


class TestSignOut(WebTestBase):
    def test_sign_out(self, client, mocker):
        mock_globus_client_cls = mocker.patch('globus_sdk.ConfidentialAppAuthClient')
        mock_globus_client = mock_globus_client_cls.return_value
        with client.session_transaction() as sess:
            sess['tokens'] = dummy_tokens
        response: Response = client.get(url_for('sign_out'))
        config = client.application.config
        mock_globus_client_cls.assert_called_once_with(config['GLOBUS_CLIENT_ID'],
                                                       config['GLOBUS_CLIENT_SECRET'])
        calls = reduce(lambda cs, token_info: cs + [
            mocker.call(token_info['access_token'], additional_params={'token_type_hint': 'access_token'}),
            mocker.call(token_info['refresh_token'], additional_params={'token_type_hint': 'refresh_token'})
        ], dummy_tokens.values(), [])
        assert len(mock_globus_client.mock_calls) == 4
        mock_globus_client.oauth2_revoke_token.assert_has_calls(calls)
        assert not session.get('tokens')
        ga_logout_url = ''.join([
            "https://auth.globus.org/v2/web/logout",
            f"?client={config['GLOBUS_CLIENT_ID']}",
            f"&redirect_uri={url_for('home', _external=True)}",
            f"&redirect_name={quote('ServiceX Portal')}"
        ])
        assert response.status_code == 302
        assert response.location == ga_logout_url
