from flask import Response, render_template

from .web_test_base import WebTestBase


class TestHome(WebTestBase):
    def test_home(self, client):
        response: Response = client.get('/')
        assert response.status_code == 200
        assert response.data.decode() == render_template('home.html')
