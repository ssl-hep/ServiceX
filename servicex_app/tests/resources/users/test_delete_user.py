from flask.wrappers import Response

from tests.web.web_test_base import WebTestBase


class TestDeleteUser(WebTestBase):
    def test_delete_user(self, mocker, user):
        client = self._test_client(mocker)
        user.id = 7
        resp_json = {'message': f'user {user.id} has been deleted'}
        resp: Response = client.delete(f'users/{user.id}')
        assert resp.status_code == 200
        assert resp.json == resp_json
        assert user.delete_from_db.called_once()
