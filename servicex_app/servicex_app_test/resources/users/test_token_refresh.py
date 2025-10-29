from flask.wrappers import Response
from flask_jwt_extended import create_refresh_token

from servicex_app_test.resource_test_base import ResourceTestBase
from servicex_app.models import UserModel


class TestTokenRefresh(ResourceTestBase):
    """Test suite for token refresh endpoint and JWT configuration."""

    def test_jwt_decode_algorithms_configured(self, client):
        """Test that JWT_DECODE_ALGORITHMS is properly configured with HS256 and RS256."""
        assert "JWT_DECODE_ALGORITHMS" in client.application.config
        algorithms = client.application.config["JWT_DECODE_ALGORITHMS"]

        assert "HS256" in algorithms, "HS256 algorithm should be configured"
        assert "RS256" in algorithms, "RS256 algorithm should be configured"

    def test_token_refresh_with_auth_disabled(self, client):
        """Test that token refresh endpoint returns graceful message when auth is disabled."""
        response: Response = client.post("/token/refresh")

        assert response.status_code == 200
        assert response.json == {
            "message": "Authentication is disabled on this instance"
        }

    def test_token_refresh_with_auth_enabled_requires_token(self):
        """Test that token refresh requires a valid token when auth is enabled."""
        client = self._test_client(extra_config={"ENABLE_AUTH": True})

        with client.application.app_context():
            response: Response = client.post("/token/refresh")
            assert response.status_code == 401

    def test_token_refresh_with_auth_enabled_and_valid_token(self, mocker):
        """Test token refresh works with valid refresh token when auth is enabled."""
        client = self._test_client(extra_config={"ENABLE_AUTH": True})

        with client.application.app_context():
            test_user = UserModel()
            test_user.email = "testuser@example.com"
            test_user.sub = "test-sub-123"
            test_user.name = "Test User"
            test_user.institution = "Test Institution"

            refresh_token = create_refresh_token(identity=test_user.email)
            test_user.refresh_token = refresh_token

            mocker.patch(
                "servicex_app.resources.users.token_refresh.UserModel.find_by_email",
                return_value=test_user,
            )

            headers = {"Authorization": f"Bearer {refresh_token}"}
            response: Response = client.post("/token/refresh", headers=headers)

            assert response.status_code == 200
            assert "access_token" in response.json

    def test_token_refresh_with_mismatched_jti(self, mocker):
        """Test that token refresh fails when JTI doesn't match stored token."""
        client = self._test_client(extra_config={"ENABLE_AUTH": True})

        with client.application.app_context():
            test_user = UserModel()
            test_user.email = "testuser@example.com"
            test_user.sub = "test-sub-123"
            test_user.name = "Test User"
            test_user.institution = "Test Institution"

            old_refresh_token = create_refresh_token(identity=test_user.email)
            new_refresh_token = create_refresh_token(identity=test_user.email)

            test_user.refresh_token = new_refresh_token

            mocker.patch(
                "servicex_app.resources.users.token_refresh.UserModel.find_by_email",
                return_value=test_user,
            )

            headers = {"Authorization": f"Bearer {old_refresh_token}"}
            response: Response = client.post("/token/refresh", headers=headers)

            assert response.status_code == 401
            assert "Invalid or outdated refresh token" in response.json.get(
                "message", ""
            )
