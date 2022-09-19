from urllib.parse import quote
from functools import reduce

from flask import Response, url_for, session

from .web_test_base import WebTestBase


class TestSignOut(WebTestBase):
    def test_sign_out(self, client, mocker, globus_client):
        oauth_tokens = self._oauth_tokens()
        with client.session_transaction() as sess:
            sess['tokens'] = oauth_tokens
        response: Response = client.get(url_for('sign_out'))
        calls = reduce(lambda cs, token_info: cs + [
            mocker.call(token_info['access_token'],
                        additional_params={'token_type_hint': 'access_token'}),
            mocker.call(token_info['refresh_token'],
                        additional_params={'token_type_hint': 'refresh_token'})
        ], oauth_tokens.values(), [])
        assert len(globus_client.mock_calls) == 2 * len(oauth_tokens)
        globus_client.oauth2_revoke_token.assert_has_calls(calls)
        assert not session.get('tokens')
        ga_logout_url = ''.join([
            "https://auth.globus.org/v2/web/logout",
            f"?client={client.application.config['GLOBUS_CLIENT_ID']}",
            f"&redirect_uri={url_for('home', _external=True)}",
            f"&redirect_name={quote('ServiceX Portal')}"
        ])
        assert response.status_code == 302
        assert response.location == ga_logout_url
