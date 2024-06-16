from textwrap import dedent

from flask import Response, url_for

from .web_test_base import WebTestBase

from servicex_app.web.servicex_file import get_correct_url


class TestServiceXFile(WebTestBase):
    module = "servicex_app.web.servicex_file"

    def test_servicex_file(self, client, user):
        cfg = {'CODE_GEN_IMAGES': {'xaod': 'asdf', 'uproot': 'asdfasdf'}}
        client.application.config.update(cfg)
        response: Response = client.get(url_for('servicex-file'))
        expected = """\
        api_endpoints:
          - name: xaod
            endpoint: http://localhost/
            token: abcdef
            codegen: xaod
            return_data: root-file
          - name: uproot
            endpoint: http://localhost/
            token: abcdef
            codegen: uproot
            return_data: root-file
        """
        assert response.data.decode() == dedent(expected)
        assert response.headers['Content-Disposition'] == 'attachment; filename=servicex.yaml'

    def test_correct_url(self, client):
        """
        Test that http endpoints are replaced with https addresses with the
        exception of http endpoints that point to localhost

        see:
        https://github.com/ssl-hep/ServiceX/issues/266
        """

        import werkzeug

        # Test provided scheme always prevails
        test_request = werkzeug.test.EnvironBuilder(path="foo/test",
                                                    base_url="http://localhost/",
                                                    headers={
                                                        "X-Scheme": "https"
                                                    }).get_request()
        test_url = "https://localhost/"
        result = get_correct_url(test_request)
        assert result == test_url

        # Test upgrade scheme to https if not localhost and no scheme provided
        request_environ = {}
        test_request = werkzeug.test.EnvironBuilder(path="foo/test",
                                                    base_url="http://test.com/",
                                                    environ_base=request_environ).get_request()
        test_url = "https://test.com/"
        result = get_correct_url(test_request)
        assert result == test_url

        # Test keep scheme if localhost
        request_environ = {}
        test_request = werkzeug.test.EnvironBuilder(path="foo/test",
                                                    base_url="http://localhost/",
                                                    environ_base=request_environ).get_request()
        test_url = "http://localhost/"
        result = get_correct_url(test_request)
        assert result == test_url
