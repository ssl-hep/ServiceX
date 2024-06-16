from flask import Response

from .web_test_base import WebTestBase


class TestAbout(WebTestBase):
    def test_about(self, client, captured_templates):
        response: Response = client.get('/about')
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "about.html"

        html = response.data.decode('utf-8')

        assert "atlasxaod" in html
        assert "sslhep/servicex_code_gen_func_adl_xaod:develop" in html

        assert "develop" in html
