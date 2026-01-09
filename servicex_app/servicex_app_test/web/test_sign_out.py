from flask import Response, url_for, session

from .web_test_base import WebTestBase


class TestSignOut(WebTestBase):
    def test_sign_out(self, mocker, oauth_client, oauth_session, client):
        oauth_tokens = self._oauth_tokens()
        with client.session_transaction() as sess:
            sess["tokens"] = oauth_tokens
        response: Response = client.get(url_for("sign_out"))
        relevant_tokens = [
            _[1] for _ in oauth_tokens.items() if _[0] in ("access_token",)
        ]
        calls = [
            mocker.call(
                "https://auth.globus.org/v2/oauth2/token/revoke", token=token_info
            )
            for token_info in relevant_tokens
        ]
        assert len(oauth_session.mock_calls) == len(relevant_tokens)
        oauth_session.revoke_token.assert_has_calls(calls)
        assert not session.get("tokens")
        ga_logout_url = "".join(
            [
                "https://auth.globus.org/v2/web/logout",
                f"?client_id={client.application.config['OAUTH_CLIENT_ID']}",
                "&id_token_hint=opaque"
                f"&post_logout_redirect_uri={url_for('home', _external=True)}",
            ]
        )
        assert response.status_code == 302
        assert response.location == ga_logout_url
