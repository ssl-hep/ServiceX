from flask import Response, url_for

from .web_test_base import WebTestBase


class TestSignIn(WebTestBase):
    def test_sign_in(self, client):
        response: Response = client.get(url_for('sign_in'))
        assert response.status_code == 302
        assert response.location == url_for('auth_callback', _external=True)
