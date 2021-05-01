from flask.wrappers import Response

from tests.web.web_test_base import WebTestBase


class TestDeleteUser(WebTestBase):
    def test_delete_user(self, mocker, client, user):
        user.id = 7
        resp_json = {'message': f'user {user.id} has been deleted'}
        resp: Response = client.delete(f'users/{user.id}')
        assert resp.status_code == 200
        assert resp.json == resp_json
        assert user.delete_from_db.called_once()

    def test_delete_user_missing(self, client):
        fake_user_id = 12345
        resp_json = {'message': f'user {fake_user_id} not found'}
        resp: Response = client.delete(f'users/{fake_user_id}')
        assert resp.status_code == 404
        assert resp.json == resp_json
