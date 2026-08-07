from flask import Response, template_rendered
from pytest import fixture

from .web_test_base import WebTestBase


class TestHome(WebTestBase):

    @fixture
    def auth_client(self):
        return self._test_client(extra_config={"ENABLE_AUTH": True})

    @fixture
    def auth_captured_templates(self, auth_client):
        recorded = []

        def record(sender, template, context, **extra):
            recorded.append((template, context))

        template_rendered.connect(record, auth_client.application)
        try:
            yield recorded
        finally:
            template_rendered.disconnect(record, auth_client.application)

    def test_home_without_auth(self, client):
        """With auth disabled, everyone lands on the global dashboard."""
        response: Response = client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/global-dashboard")

    def test_home_signed_out(self, auth_client, auth_captured_templates):
        response: Response = auth_client.get("/")
        assert response.status_code == 200
        template, _ = auth_captured_templates[0]
        assert template.name == "home.html"

    def test_home_signed_in(self, auth_client, user):
        with auth_client.session_transaction() as sess:
            sess["is_authenticated"] = True
            sess["user_id"] = user.id
        response: Response = auth_client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
