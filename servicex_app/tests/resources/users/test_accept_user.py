from tests.web.web_test_base import WebTestBase


class TestAcceptUser(WebTestBase):
    def test_accept_user(self, user, client):
        user.pending = True
        response = client.post('/accept', json={"email": user.email})
        assert response.status_code == 200
        assert not user.pending
        assert user.save_to_db.called_once()

    def test_accept_user_missing(self, client, mocker):
        mocker.patch('servicex.models.UserModel.find_by_email', return_value=None)
        response = client.post('/accept', json={"email": 'janedoe@example.com'})
        assert response.status_code == 404
