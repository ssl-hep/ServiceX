import requests
from flask import current_app, render_template

from servicex_app.reliable_requests import servicex_retry, REQUEST_TIMEOUT


class MailgunAdaptor:
    def __init__(self):
        self.api_key = current_app.config.get('MAILGUN_API_KEY')
        self.domain = current_app.config.get('MAILGUN_DOMAIN')
        self.endpoint = f"https://api.mailgun.net/v3/{self.domain}/messages"

    @servicex_retry()
    def post_mailgun(self, data) -> requests.Response:
        res = requests.post(self.endpoint, data,
                            auth=("api", self.api_key),
                            timeout=REQUEST_TIMEOUT)
        return res

    def send(self, email: str, template_name: str):
        """
        Sends an email to the given address using the given template.
        :param email: Email address of recipient.
        :param template_name: Name of HTML template file.
        """
        if not self.api_key or not self.domain:
            return
        data = {
            "from": f"ServiceX <noreply@{self.domain}>",
            "to": [email],
            "subject": "Welcome to ServiceX!",
            "html": render_template(f"emails/{template_name}")
        }

        res = self.post_mailgun(data)
        res.raise_for_status()
