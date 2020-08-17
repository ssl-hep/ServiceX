from flask import Response, url_for

from .web_test_base import WebTestBase


class TestHome(WebTestBase):
    def test_home(self, client):
        response: Response = client.get(url_for('sign_in'))
        assert response.status_code == 302
        assert response.location == url_for('auth_callback', _external=True)
