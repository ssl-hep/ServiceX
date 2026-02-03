"""Tests for token verification module."""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from servicex_app.token_verification import (
    JWKSCache,
    OIDCMetadataCache,
    TokenVerificationError,
    VerificationResult,
    clear_caches,
    is_token_expiring_soon,
    verify_token,
    verify_token_introspection,
    verify_token_local,
)


@pytest.fixture
def mock_app():
    """Create a mock Flask app with config."""
    app = MagicMock()
    app.config = {
        "OAUTH_METADATA_URL": "https://example.com/.well-known/openid-configuration",
        "OAUTH_CLIENT_ID": "test-client-id",
        "OAUTH_CLIENT_SECRET": "test-client-secret",
        "ENABLE_AUTH": True,
    }
    app.logger = MagicMock()
    return app


@pytest.fixture
def mock_oidc_metadata():
    """Mock OIDC metadata response."""
    return {
        "issuer": "https://example.com",
        "authorization_endpoint": "https://example.com/authorize",
        "token_endpoint": "https://example.com/token",
        "userinfo_endpoint": "https://example.com/userinfo",
        "jwks_uri": "https://example.com/.well-known/jwks.json",
        "introspection_endpoint": "https://example.com/introspect",
    }


@pytest.fixture
def mock_jwks():
    """Mock JWKS response with an RSA key."""
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-id",
                "use": "sig",
                "alg": "RS256",
                "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
                "e": "AQAB",
            }
        ]
    }


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear caches before each test."""
    clear_caches()
    yield
    clear_caches()


class TestJWKSCache:
    """Tests for JWKS caching."""

    def test_cache_stores_keys(self):
        """Test that keys are cached after first fetch."""
        cache = JWKSCache(ttl_seconds=3600)

        with patch("servicex_app.token_verification.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "test",
                        "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
                        "e": "AQAB",
                    }
                ]
            }
            mock_get.return_value = mock_response

            # First call should fetch
            keys1 = cache.get_keys("https://example.com/jwks")
            assert mock_get.call_count == 1

            # Second call should use cache
            keys2 = cache.get_keys("https://example.com/jwks")
            assert mock_get.call_count == 1  # No additional fetch

    def test_cache_expires(self):
        """Test that cache expires after TTL."""
        cache = JWKSCache(ttl_seconds=1)

        with patch("servicex_app.token_verification.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "test",
                        "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
                        "e": "AQAB",
                    }
                ]
            }
            mock_get.return_value = mock_response

            cache.get_keys("https://example.com/jwks")
            assert mock_get.call_count == 1

            # Wait for TTL to expire
            time.sleep(1.1)

            cache.get_keys("https://example.com/jwks")
            assert mock_get.call_count == 2  # Should fetch again

    def test_force_refresh(self):
        """Test force refresh bypasses cache."""
        cache = JWKSCache(ttl_seconds=3600)

        with patch("servicex_app.token_verification.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "test",
                        "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
                        "e": "AQAB",
                    }
                ]
            }
            mock_get.return_value = mock_response

            cache.get_keys("https://example.com/jwks")
            cache.get_keys("https://example.com/jwks", force_refresh=True)
            assert mock_get.call_count == 2


class TestOIDCMetadataCache:
    """Tests for OIDC metadata caching."""

    def test_metadata_cached(self):
        """Test that metadata is cached."""
        cache = OIDCMetadataCache(ttl_seconds=3600)

        with patch("servicex_app.token_verification.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"issuer": "https://example.com"}
            mock_get.return_value = mock_response

            metadata1 = cache.get_metadata("https://example.com/.well-known/openid-configuration")
            metadata2 = cache.get_metadata("https://example.com/.well-known/openid-configuration")

            assert mock_get.call_count == 1
            assert metadata1 == metadata2


class TestVerifyTokenLocal:
    """Tests for local JWT verification."""

    def test_missing_metadata_url(self, mock_app):
        """Test error when metadata URL not configured."""
        mock_app.config["OAUTH_METADATA_URL"] = None

        with patch("servicex_app.token_verification.current_app", mock_app):
            result = verify_token_local("some.jwt.token")
            assert not result.valid
            assert "not configured" in result.error

    def test_expired_token(self, mock_app, mock_oidc_metadata, mock_jwks):
        """Test that expired tokens are rejected."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                def mock_response_side_effect(url, **kwargs):
                    response = MagicMock()
                    if "openid-configuration" in url:
                        response.json.return_value = mock_oidc_metadata
                    else:
                        response.json.return_value = mock_jwks
                    return response

                mock_get.side_effect = mock_response_side_effect

                # Create an expired token (this is a placeholder - real test would use a real JWT)
                with patch("servicex_app.token_verification.jwt.decode") as mock_decode:
                    from authlib.jose.errors import ExpiredTokenError as AuthlibExpiredTokenError

                    mock_decode.side_effect = AuthlibExpiredTokenError()

                    result = verify_token_local("expired.jwt.token")
                    assert not result.valid
                    assert "expired" in result.error.lower()

    def test_invalid_signature(self, mock_app, mock_oidc_metadata, mock_jwks):
        """Test that tokens with invalid signatures are rejected."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                def mock_response_side_effect(url, **kwargs):
                    response = MagicMock()
                    if "openid-configuration" in url:
                        response.json.return_value = mock_oidc_metadata
                    else:
                        response.json.return_value = mock_jwks
                    return response

                mock_get.side_effect = mock_response_side_effect

                with patch("servicex_app.token_verification.jwt.decode") as mock_decode:
                    from authlib.jose.errors import BadSignatureError

                    # BadSignatureError requires a result argument
                    mock_decode.side_effect = BadSignatureError(result=None)

                    result = verify_token_local("bad.signature.token")
                    assert not result.valid
                    assert "signature" in result.error.lower()


class TestVerifyTokenIntrospection:
    """Tests for token introspection."""

    def test_introspection_active_token(self, mock_app, mock_oidc_metadata):
        """Test introspection with an active token."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                with patch("servicex_app.token_verification.requests.post") as mock_post:
                    # Mock metadata fetch
                    mock_get_response = MagicMock()
                    mock_get_response.json.return_value = mock_oidc_metadata
                    mock_get.return_value = mock_get_response

                    # Mock introspection response
                    mock_post_response = MagicMock()
                    mock_post_response.json.return_value = {
                        "active": True,
                        "sub": "user-123",
                        "email": "user@example.com",
                        "exp": int(time.time()) + 3600,
                    }
                    mock_post.return_value = mock_post_response

                    result = verify_token_introspection("valid-token")

                    assert result.valid
                    assert result.claims["sub"] == "user-123"
                    assert result.method == "introspection"

    def test_introspection_inactive_token(self, mock_app, mock_oidc_metadata):
        """Test introspection with an inactive/revoked token."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                with patch("servicex_app.token_verification.requests.post") as mock_post:
                    mock_get_response = MagicMock()
                    mock_get_response.json.return_value = mock_oidc_metadata
                    mock_get.return_value = mock_get_response

                    mock_post_response = MagicMock()
                    mock_post_response.json.return_value = {"active": False}
                    mock_post.return_value = mock_post_response

                    result = verify_token_introspection("revoked-token")

                    assert not result.valid
                    assert "not active" in result.error.lower()

    def test_introspection_no_endpoint(self, mock_app):
        """Test introspection when endpoint not available."""
        mock_oidc_metadata_no_introspection = {
            "issuer": "https://example.com",
            "jwks_uri": "https://example.com/jwks",
        }

        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                mock_get_response = MagicMock()
                mock_get_response.json.return_value = mock_oidc_metadata_no_introspection
                mock_get.return_value = mock_get_response

                result = verify_token_introspection("some-token")

                assert not result.valid
                assert "not available" in result.error.lower()

    def test_introspection_missing_credentials(self, mock_app, mock_oidc_metadata):
        """Test introspection fails without client credentials."""
        mock_app.config["OAUTH_CLIENT_SECRET"] = None

        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.requests.get") as mock_get:
                mock_get_response = MagicMock()
                mock_get_response.json.return_value = mock_oidc_metadata
                mock_get.return_value = mock_get_response

                result = verify_token_introspection("some-token")

                assert not result.valid
                assert "credentials" in result.error.lower()


class TestVerifyToken:
    """Tests for the unified verify_token function."""

    def test_method_local(self, mock_app, mock_oidc_metadata, mock_jwks):
        """Test explicit local verification method."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                mock_local.return_value = VerificationResult(valid=True, method="local")

                result = verify_token("test-token", method="local")

                mock_local.assert_called_once()
                assert result.method == "local"

    def test_method_introspection(self, mock_app, mock_oidc_metadata):
        """Test explicit introspection method."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch(
                "servicex_app.token_verification.verify_token_introspection"
            ) as mock_introspect:
                mock_introspect.return_value = VerificationResult(
                    valid=True, method="introspection"
                )

                result = verify_token("test-token", method="introspection")

                mock_introspect.assert_called_once()
                assert result.method == "introspection"

    def test_method_auto_local_success(self, mock_app):
        """Test auto method uses local when it succeeds."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                with patch(
                    "servicex_app.token_verification.verify_token_introspection"
                ) as mock_introspect:
                    mock_local.return_value = VerificationResult(valid=True, method="local")

                    result = verify_token("test-token", method="auto")

                    mock_local.assert_called_once()
                    mock_introspect.assert_not_called()
                    assert result.valid

    def test_method_auto_fallback_to_introspection(self, mock_app):
        """Test auto method falls back to introspection on decode error."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                with patch(
                    "servicex_app.token_verification.verify_token_introspection"
                ) as mock_introspect:
                    mock_local.return_value = VerificationResult(
                        valid=False, error="Failed to decode token", method="local"
                    )
                    mock_introspect.return_value = VerificationResult(
                        valid=True, method="introspection"
                    )

                    result = verify_token("opaque-token", method="auto")

                    mock_local.assert_called_once()
                    mock_introspect.assert_called_once()
                    assert result.valid
                    assert result.method == "introspection"

    def test_config_override(self, mock_app):
        """Test that config can override verification method."""
        mock_app.config["TOKEN_VERIFICATION_METHOD"] = "introspection"

        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch(
                "servicex_app.token_verification.verify_token_introspection"
            ) as mock_introspect:
                mock_introspect.return_value = VerificationResult(
                    valid=True, method="introspection"
                )

                # Even though we pass method="local", config should override
                result = verify_token("test-token", method="local")

                mock_introspect.assert_called_once()


class TestIsTokenExpiringSoon:
    """Tests for token expiration checking."""

    def test_token_expiring_soon(self, mock_app):
        """Test detection of token expiring within threshold."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                # Token expires in 2 minutes
                from datetime import timedelta

                expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
                mock_local.return_value = VerificationResult(
                    valid=True,
                    method="local",
                    expires_at=expires_at,
                )

                is_expiring, exp_time = is_token_expiring_soon(
                    "test-token", threshold_seconds=300
                )

                assert is_expiring  # 2 min < 5 min threshold
                assert exp_time is not None

    def test_token_not_expiring_soon(self, mock_app):
        """Test token not expiring within threshold."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                # Token expires in 1 hour
                from datetime import timedelta

                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                mock_local.return_value = VerificationResult(
                    valid=True,
                    method="local",
                    expires_at=expires_at,
                )

                is_expiring, exp_time = is_token_expiring_soon(
                    "test-token", threshold_seconds=300
                )

                assert not is_expiring  # 1 hour > 5 min threshold

    def test_invalid_token_treated_as_expiring(self, mock_app):
        """Test that invalid tokens are treated as expiring."""
        with patch("servicex_app.token_verification.current_app", mock_app):
            with patch("servicex_app.token_verification.verify_token_local") as mock_local:
                mock_local.return_value = VerificationResult(
                    valid=False,
                    error="Invalid token",
                    method="local",
                )

                is_expiring, exp_time = is_token_expiring_soon("invalid-token")

                assert is_expiring
                assert exp_time is None


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = VerificationResult(
            valid=True,
            claims={"sub": "user-123"},
            method="local",
        )
        assert result.valid
        assert result.claims["sub"] == "user-123"
        assert result.error is None

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = VerificationResult(
            valid=False,
            error="Token expired",
            method="local",
        )
        assert not result.valid
        assert result.error == "Token expired"
        assert result.claims is None
