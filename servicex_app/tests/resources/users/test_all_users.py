from flask.wrappers import Response

from tests.web.web_test_base import WebTestBase


class TestAllUsers(WebTestBase):
    def test_get_users(self, client, mocker):
        resp_json = {'users': []}
        mock = mocker.patch('servicex.models.UserModel.return_all',
                            return_value=resp_json)
        response: Response = client.get('/users')
        assert response.status_code == 200
        assert mock.called_once()
        assert response.json == resp_json

    def test_delete_users(self, client, mocker):
        resp_json = {'message': '0 row(s) deleted'}
        mock = mocker.patch('servicex.models.UserModel.delete_all',
                            return_value=resp_json)
        response: Response = client.delete('/users')
        assert response.status_code == 200
        assert mock.called_once()
        assert response.json == resp_json
