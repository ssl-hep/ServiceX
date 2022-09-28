from flask import url_for, Response, make_response
from flask_jwt_extended import create_access_token

from tests.web.web_test_base import WebTestBase


def fake_route() -> Response:
    return make_response({'data': 'abc123'})


class TestDecorators(WebTestBase):
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

    def test_oauth_decorator_not_signed_in(self):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import oauth_required
            decorated = oauth_required(fake_route)
            response = decorated()
            assert response.status_code == 302
            assert response.location == url_for('sign_in')

    def test_oauth_decorator_not_saved(self):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
        response: Response = client.get(url_for('profile'))
        assert response.status_code == 302
        assert response.location == url_for('create_profile', _external=True)

    def test_oauth_decorator_saved(self, client, user, captured_templates):
        client.application.config['ENABLE_AUTH'] = True
        user.id = 7
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
            sess['user_id'] = user.id
        resp: Response = client.get(url_for('profile'))
        assert resp.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "profile.html"
        assert context["user"] == user

    def test_auth_decorator_auth_disabled(self, client):
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_auth_decorator_user_deleted(self, mocker, mock_jwt_extended):
        mocker.patch('servicex.decorators.UserModel.find_by_sub',
                     return_value=None)
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_auth_decorator_user_pending(self, mock_jwt_extended, user):
        user.pending = True
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            from servicex.decorators import auth_required
            decorated = auth_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_auth_decorator_authorized(self, mocker, mock_jwt_extended, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
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

    def test_admin_decorator_unauthorized(self, mocker, mock_jwt_extended, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        user.admin = False
        with client.application.app_context():
            from servicex.decorators import admin_required
            decorated = admin_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 401

    def test_admin_decorator_authorized(self, mock_jwt_extended, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        user.admin = True
        with client.application.app_context():
            from servicex.decorators import admin_required
            decorated = admin_required(fake_route)
            response: Response = decorated()
            assert response.status_code == 200

    def test_auth_decorator_integration_auth_disabled(self, mocker, client):
        fake_transform_id = 123
        data = {'id': fake_transform_id}
        mock = mocker.patch('servicex.resources.transformation.get_one'
                            '.TransformRequest.lookup').return_value
        mock.to_json.return_value = data
        with client.application.app_context():
            response: Response = client.get(f'servicex/transformation/{fake_transform_id}')
            print(response.data)
            assert response.status_code == 200
            assert response.json == data

    def test_auth_decorator_integration_no_header(self):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123')
            print(response.data)
            assert response.status_code == 401
            assert response.json['message'] == 'Missing Authorization Header'

    def test_auth_decorator_integration_user_deleted(self):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123',
                                            headers=self.fake_header())
            assert response.status_code == 401
            assert 'deleted' in response.json['message']

    def test_auth_decorator_integration_user_pending(self, mocker, user):
        user.pending = True
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('servicex/transformation/123',
                                            headers=self.fake_header())
            assert response.status_code == 401
            assert 'pending' in response.json['message']

    def test_auth_decorator_integration_authorized(self, mocker, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        fake_transform_id = 123
        data = {'id': fake_transform_id}
        mock = mocker.patch('servicex.resources.transformation.get_one'
                            '.TransformRequest.lookup').return_value
        mock.submitted_by = user.id
        mock.to_json.return_value = data
        with client.application.app_context():
            response: Response = client.get(f'servicex/transformation/{fake_transform_id}',
                                            headers=self.fake_header())
            print(response.data)
            assert response.status_code == 200
            assert response.json == data

    def test_auth_decorator_integration_oauth(self, mocker, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        fake_transform_id = 123
        data = {'id': fake_transform_id}
        mock = mocker.patch('servicex.resources.transformation.get_one'
                            '.TransformRequest.lookup').return_value
        mock.submitted_by = user.id
        mock.to_json.return_value = data
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
        with client.application.app_context():
            response: Response = client.get(f'servicex/transformation/{fake_transform_id}')
            print(response.data)
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_auth_disabled(self, mocker, client):
        data = {'users': [{'id': 1234}]}
        mocker.patch('servicex.models.UserModel.return_all', return_value=data)
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_no_header(self):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 401
            assert response.json['message'] == 'Missing Authorization Header'

    def test_admin_decorator_integration_not_authorized(self, user):
        user.admin = False
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users', headers=self.fake_header())
            assert response.status_code == 401
            assert 'restricted' in response.json['message']

    def test_admin_decorator_integration_authorized(self, mocker, user):
        user.admin = True
        data = {'users': [{'id': 1234}]}
        mocker.patch('servicex.models.UserModel.return_all', return_value=data)
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            response: Response = client.get('users', headers=self.fake_header())
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_oauth_authorized(self, mocker, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        data = {'users': [{'id': 1234}]}
        mocker.patch('servicex.models.UserModel.return_all', return_value=data)
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
            sess['admin'] = True
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 200
            assert response.json == data

    def test_admin_decorator_integration_oauth_not_authorized(self, user):
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.session_transaction() as sess:
            sess['is_authenticated'] = True
            sess['admin'] = False
        with client.application.app_context():
            response: Response = client.get('users')
            assert response.status_code == 401
            assert 'restricted' in response.json['message']
