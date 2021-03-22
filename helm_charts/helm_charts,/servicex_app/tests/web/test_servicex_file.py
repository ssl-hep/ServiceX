from textwrap import dedent

from flask import Response, url_for, get_flashed_messages

from .web_test_base import WebTestBase

from servicex.web.servicex_file import correct_url

class TestServiceXFile(WebTestBase):
    def test_servicex_file(self, client, user):
        cfg = {'CODE_GEN_IMAGE': 'sslhep/servicex_code_gen_func_adl_xaod:develop'}
        client.application.config.update(cfg)
        response: Response = client.get(url_for('servicex-file'))
        expected = """\
        api_endpoints:
          - endpoint: http://localhost/
            token: abcdef
            type: xaod
        """
        assert response.data.decode() == dedent(expected)
        assert response.headers['Content-Disposition'] == 'attachment; filename=servicex.yaml'

    def test_servicex_file_no_match(self, client):
        cfg = {'CODE_GEN_IMAGE': 'sslhep/servicex_code_gen_func_adl:develop'}
        client.application.config.update(cfg)
        response: Response = client.get(url_for('servicex-file'))
        assert response.status_code == 302
        flashed_messages = get_flashed_messages()
        assert flashed_messages
        assert "Unable to infer filetype" in flashed_messages[0]

    def test_servicex_file_ambiguous_match(self, client):
        cfg = {'CODE_GEN_IMAGE': 'sslhep/servicex_code_gen_func_adl_xaod_uproot:develop'}
        client.application.config.update(cfg)
        response: Response = client.get(url_for('servicex-file'))
        assert response.status_code == 302
        flashed_messages = get_flashed_messages()
        assert flashed_messages
        assert "Unable to infer filetype" in flashed_messages[0]

    def test_correct_url(self, client):
        """
        Test that http endpoints are replaced with https addresses with the
        exception of http endpoints that point to localhost

        see:
        https://github.com/ssl-hep/ServiceX/issues/266
        """
        test_url = "http://localhost/foo/test"
        result = correct_url(test_url)
        assert result == test_url

        test_url = "https://localhost/foo/test"
        result = correct_url(test_url)
        assert result == test_url

        test_url = "http://test.com/foo/test"
        result = correct_url(test_url)
        assert result == test_url.replace("http", "https")

        test_url = "https://test.com:8080/foo/test"
        result = correct_url(test_url)
        assert result == test_url
