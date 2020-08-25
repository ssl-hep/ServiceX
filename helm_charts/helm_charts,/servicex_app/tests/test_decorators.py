from flask import url_for, render_template, Response, make_response
from pytest import fixture

from tests.web.web_test_base import WebTestBase


def fake_route() -> Response:
    return make_response({'data': 'abc123'})


class TestDecorators(WebTestBase):
    @fixture
    def mock_jwt_required(self, mocker):
        mocker.patch('servicex.decorators.jwt_required',
                     side_effect=lambda f: f)

    def test_oauth_decorator_auth_disabled(self, client):
        with client.application.app_context():
            from servicex.decorators import oauth_required
            decorated = oauth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_oauth_decorator_not_signed_in(self, mocker):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import oauth_required
            decorated = oauth_required(fake_route)
            response = decorated()
            assert response.status_code == 302
            assert response.location == url_for('sign_in')

    def test_oauth_decorator_not_saved(self, mocker):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
        response: Response = client.get(url_for('profile'))
        assert response.status_code == 302
        assert response.location == url_for('create_profile', _external=True)

    def test_oauth_decorator_saved(self, client, user):
        client.application.config['ENABLE_AUTH'] = True
        user.id = 7
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
            sess['user_id'] = user.id
        resp: Response = client.get(url_for('profile'))
        assert resp.status_code == 200
        assert resp.data.decode() == render_template('profile.html', user=user)

    def test_auth_decorator_auth_disabled(self, client):
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_auth_decorator_user_deleted(self, mocker):
        mocker.patch('servicex.decorators.UserModel.find_by_sub',
                     return_value=None)
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_auth_decorator_user_pending(self, mocker, mock_jwt_required, user):
        user.pending = True
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_auth_decorator_authorized(self, mocker, mock_jwt_required, user):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_admin_decorator_auth_disabled(self, client):
        with client.application.app_context():
            from servicex.decorators import admin_required
            decorated = admin_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_admin_decorator_unauthorized(self, mocker, mock_jwt_required, user):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        user.admin = False
        with client.application.app_context():
            from servicex.decorators import admin_required
            decorated = admin_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_admin_decorator_authorized(self, mocker, mock_jwt_required, user):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        user.admin = True
        with client.application.app_context():
            from servicex.decorators import admin_required
            decorated = admin_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

