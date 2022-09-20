from flask import Response, url_for

from .web_test_base import WebTestBase


class TestViewProfile(WebTestBase):
    def test_view_profile(self, user, client, captured_templates):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        response: Response = client.get(url_for('profile'))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "profile.html"
        assert context["user"] == user
