from flask.wrappers import Response

from servicex_app_test.web.web_test_base import WebTestBase


class TestPendingUsers(WebTestBase):
    def test_get_pending_users(self, client, mocker):
        resp_json = {"users": []}
        mock = mocker.patch(
            "servicex_app.models.UserModel.return_all_pending", return_value=resp_json
        )
        response: Response = client.get("/pending")
        assert response.status_code == 200
        mock.assert_called_once()
        assert response.json == resp_json

    def test_delete_pending_users(self, client):
        from servicex_app.models import UserModel

        with client.application.app_context():
            pending_user = self._test_user()
            pending_user.pending = True
            pending_user.save_to_db()

            accepted_user = self._test_user()
            accepted_user.email = "john@example.com"
            accepted_user.sub = "johndoe"
            accepted_user.refresh_token = "fedcba"
            accepted_user.pending = False
            accepted_user.save_to_db()

            response: Response = client.delete("/pending")
            assert response.status_code == 200
            assert response.json == {"message": "1 row(s) deleted"}
            assert [user.email for user in UserModel.query.all()] == [
                accepted_user.email
            ]
