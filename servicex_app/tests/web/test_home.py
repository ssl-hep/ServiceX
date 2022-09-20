from flask import Response

from .web_test_base import WebTestBase


class TestHome(WebTestBase):
    def test_home(self, client, captured_templates):
        response: Response = client.get('/')
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "home.html"
