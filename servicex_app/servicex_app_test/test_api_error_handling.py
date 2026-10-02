from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from servicex_app_test.resource_test_base import ResourceTestBase


class TestApiErrorHandling(ResourceTestBase):
    """
    Error responses as production sees them. The shared test config sets
    TESTING, which makes flask-restful re-raise every exception and hides how
    errors are answered in a deployment, so these tests turn it off.
    """

    @pytest.fixture
    def prod_client(self):
        return self._test_client(extra_config={"ENABLE_AUTH": True, "TESTING": False})

    def test_refresh_without_token_is_401(self, prod_client):
        response = prod_client.post("/token/refresh")
        assert response.status_code == 401
        assert response.json == {"msg": "Missing Authorization Header"}

    def test_refresh_with_expired_token_is_401(self, prod_client):
        with prod_client.application.app_context():
            token = create_refresh_token(
                "someone@example.com", expires_delta=timedelta(seconds=-60)
            )
        response = prod_client.post(
            "/token/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json == {"msg": "Token has expired"}

    def test_refresh_with_access_token_is_422(self, prod_client):
        with prod_client.application.app_context():
            token = create_access_token("someone@example.com")
        response = prod_client.post(
            "/token/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
        assert response.json == {"msg": "Only refresh tokens are allowed"}

    def test_refresh_with_garbage_token_is_422(self, prod_client):
        response = prod_client.post(
            "/token/refresh", headers={"Authorization": "Bearer garbage"}
        )
        assert response.status_code == 422
        assert "msg" in response.json

    def test_auth_required_with_expired_token_is_401(self, prod_client):
        with prod_client.application.app_context():
            token = create_access_token(
                "someone@example.com", expires_delta=timedelta(seconds=-60)
            )
        response = prod_client.get(
            "/servicex/datasets", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json == {"msg": "Token has expired"}

    def test_auth_required_with_garbage_token_is_422(self, prod_client):
        response = prod_client.get(
            "/servicex/datasets", headers={"Authorization": "Bearer garbage"}
        )
        assert response.status_code == 422
        assert "msg" in response.json

    def test_other_errors_keep_json_500(self, mocker):
        client = self._test_client(extra_config={"TESTING": False})
        mocker.patch(
            "servicex_app.resources.datasets.get_all.Dataset.get_all",
            side_effect=RuntimeError("boom"),
        )
        response = client.get("/servicex/datasets")
        assert response.status_code == 500
        assert response.json == {"message": "Internal Server Error"}
