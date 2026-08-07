from flask import Response
from pytest import fixture

from .web_test_base import WebTestBase


class TestHome(WebTestBase):

    @fixture
    def auth_client(self):
        return self._test_client(extra_config={"ENABLE_AUTH": True})

    def test_home_without_auth(self, client):
        """With auth disabled, everyone lands on the global dashboard."""
        response: Response = client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/global-dashboard")

    def test_home_signed_out(self, auth_client):
        """With auth enabled, signed-out visitors are sent to sign in."""
        response: Response = auth_client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/sign-in")

    def test_home_signed_in(self, auth_client, user):
        with auth_client.session_transaction() as sess:
            sess["is_authenticated"] = True
            sess["user_id"] = user.id
        response: Response = auth_client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
