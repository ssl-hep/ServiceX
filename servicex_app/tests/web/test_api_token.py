from flask import url_for, Response

from .web_test_base import WebTestBase


class TestApiToken(WebTestBase):
    def test_api_token(self, client, user, db):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        user.refresh_token = 'jwt:refresh'
        response: Response = client.get(url_for('api_token'))
        assert user.refresh_token != 'jwt:refresh'
        assert db.session.commit.called_once()
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)
