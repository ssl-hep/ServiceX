from flask import url_for, render_template, Response, make_response
from flask_jwt_extended import create_access_token
from pytest import fixture

from tests.web.web_test_base import WebTestBase


def fake_route() -> Response:
    return make_response({'data': 'abc123'})


class TestDecorators(WebTestBase):
    @fixture
    def mock_jwt_required(self, mocker):
        """
        During unit tests, the jwt_required decorator from Flask-JWT-extended
        is simply mocked to act as the identity function.
        """
        mocker.patch('servicex.decorators.jwt_required',
                     side_effect=lambda f: f)

    @staticmethod
    def fake_header():
        access_token = create_access_token(identity='abcd')
        return {'Authorization': f'Bearer {access_token}'}

    def test_oauth_decorator_auth_disabled(self, client):
        from servicex.decorators import oauth_required
        with client.application.app_context():
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

    def test_auth_decorator_user_deleted(self, mocker, mock_jwt_required):
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

    def test_auth_decorator_integration_auth_disabled(self, mocker):
        fake_transform_id = 123
        data = {'id': fake_transform_id}
        mocker.patch('servicex.resources.query_transformation_request.TransformRequest.to_json',
                     return_value=data)
        client = self._test_client(mocker)
        with client.application.app_context():
            response: Response = client.get(f'servicex/transformation/{fake_transform_id}')
            assert response.status_code == 200
            assert response.json == data

    def test_auth_decorator_integration_no_header(self, mocker):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123')
            assert response.status_code == 401
            assert response.json['msg'] == 'Missing Authorization Header'

    def test_auth_decorator_integration_user_deleted(self, mocker):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123',
                                            headers=self.fake_header())
            assert response.status_code == 401
            assert 'deleted' in response.json['message']

    def test_auth_decorator_integration_user_pending(self, mocker, user):
        user.pending = True
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123',
                                            headers=self.fake_header())
            assert response.status_code == 401
            assert 'pending' in response.json['message']

    def test_auth_decorator_integration_authorized(self, mocker, user):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        fake_transform_id = 123
        data = {'id': fake_transform_id}
        mocker.patch('servicex.resources.query_transformation_request.TransformRequest.to_json',
                     return_value=data)
        with client.application.app_context():
            response: Response = client.get(f'servicex/transformation/{fake_transform_id}',
                                            headers=self.fake_header())
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_auth_disabled(self, mocker):
        data = {'users': [{'id': 1234}]}
        mocker.patch('servicex.models.UserModel.return_all', return_value=data)
        client = self._test_client(mocker)
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_no_header(self, mocker):
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 401
            assert response.json['msg'] == 'Missing Authorization Header'

    def test_admin_decorator_integration_not_authorized(self, mocker, user):
        user.admin = False
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users', headers=self.fake_header())
            assert response.status_code == 401
            assert 'restricted' in response.json['message']

    def test_admin_decorator_integration_authorized(self, mocker, user):
        user.admin = True
        data = {'users': [{'id': 1234}]}
        mocker.patch('servicex.models.UserModel.return_all', return_value=data)
        client = self._test_client(mocker, extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users', headers=self.fake_header())
            assert response.status_code == 200
            assert response.json == data
