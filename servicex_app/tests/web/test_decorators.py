from flask import url_for, render_template, Response

from .web_test_base import WebTestBase


class TestDecorators(WebTestBase):
    def test_auth_decorator_auth_disabled(self, client):
        with client.application.app_context():
            from servicex.web.decorators import authenticated
            from servicex.web import home
            decorated = authenticated(home)
            assert decorated() == home()

    def test_auth_decorator_not_signed_in(self, mocker):
        client = self._test_client(mocker,
                                   additional_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.web.decorators import authenticated
            from servicex.web import home
            decorated = authenticated(home)
            response = decorated()
            assert response.status_code == 302
            assert response.location == url_for('sign_in')

    def test_auth_decorator_not_saved(self, mocker, new_user):
        client = self._test_client(mocker,
                                   additional_config={'ENABLE_AUTH': True})
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
        response: Response = client.get(url_for('profile'))
        assert response.status_code == 302
        assert response.location == url_for('create_profile', _external=True)

    def test_auth_decorator_saved(self, client, user):
        client.application.config['ENABLE_AUTH'] = True
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
            sess['user_id'] = user.id
        response: Response = client.get(url_for('profile'))
        assert response.status_code == 200
        assert response.data.decode() == render_template('profile.html',
                                                         user=user)
