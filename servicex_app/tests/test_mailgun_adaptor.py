from flask import render_template

from servicex.mailgun_adaptor import MailgunAdaptor
from tests.resource_test_base import ResourceTestBase


class TestMailgunAdaptor(ResourceTestBase):
    def test_noop(self, mocker, client):
        import requests
        mock_post = mocker.patch.object(requests, "post")
        with client.application.app_context():
            mailgun = MailgunAdaptor()
            mailgun.send('janedoe@example.com', 'welcome.html')
            mock_post.assert_not_called()

    def test_init(self):
        config = {'MAILGUN_API_KEY': 'key123', 'MAILGUN_DOMAIN': 'example.com'}
        client = self._test_client(extra_config=config)
        with client.application.app_context():
            mailgun = MailgunAdaptor()
            assert mailgun.api_key == config['MAILGUN_API_KEY']
            assert mailgun.domain == config['MAILGUN_DOMAIN']

    def test_send(self, mocker):
        import requests
        mock_post = mocker.patch.object(requests, "post")
        config = {'MAILGUN_API_KEY': 'key123', 'MAILGUN_DOMAIN': 'example.com'}
        client = self._test_client(extra_config=config)
        with client.application.app_context():
            mailgun = MailgunAdaptor()
            email, template_name = 'janedoe@example.com', 'welcome.html'
            mailgun.send(email, template_name)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            endpoint_arg, data_arg = args
            assert data_arg['to'] == [email]
            assert data_arg['html'] == render_template(f"emails/{template_name}")
