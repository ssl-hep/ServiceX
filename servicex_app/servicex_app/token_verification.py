"""
Token Verification Module

Provides both local JWT verification (using JWKS) and external token
introspection for verifying SSO tokens from OIDC providers.

Local verification:
- Fetches JWKS from the provider's jwks_uri endpoint
- Caches keys to avoid repeated network calls
- Verifies signature, expiration, issuer, and audience

Token introspection:
- Calls the provider's introspection_endpoint (RFC 7662)
- Returns real-time token validity status
- Required for detecting token revocation
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import (
    BadSignatureError,
    DecodeError,
    ExpiredTokenError,
    InvalidClaimError,
)
from flask import current_app, g


class TokenVerificationError(Exception):
    """Base exception for token verification errors."""

    pass


class TokenExpiredError(TokenVerificationError):
    """Token has expired."""

    pass


class TokenInvalidError(TokenVerificationError):
    """Token signature or structure is invalid."""

    pass


class TokenRevokedError(TokenVerificationError):
    """Token has been revoked (detected via introspection)."""

    pass


class TokenIntrospectionError(TokenVerificationError):
    """Error during token introspection request."""

    pass


@dataclass
class VerificationResult:
    """Result of token verification."""

    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    method: str = "unknown"  # "local" or "introspection"
    expires_at: Optional[datetime] = None


class JWKSCache:
    """
    Thread-safe cache for JWKS (JSON Web Key Sets).

    Caches the public keys used for JWT verification to avoid
    fetching them on every request. Keys are refreshed when:
    - Cache TTL expires
    - A key ID (kid) is not found in the cache
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the JWKS cache.

        Args:
            ttl_seconds: Time-to-live for cached keys (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[JsonWebKey, float]] = {}
        self._ttl = ttl_seconds

    def get_keys(self, jwks_uri: str, force_refresh: bool = False) -> JsonWebKey:
        """
        Get JWKS from cache or fetch from the provider.

        Args:
            jwks_uri: URL to the JWKS endpoint
            force_refresh: Force a refresh even if cache is valid

        Returns:
            JsonWebKey set for signature verification
        """
        now = time.time()
        cached = self._cache.get(jwks_uri)

        if cached and not force_refresh:
            keys, cached_at = cached
            if now - cached_at < self._ttl:
                return keys

        # Fetch fresh keys
        try:
            response = requests.get(jwks_uri, timeout=10)
            response.raise_for_status()
            jwks_data = response.json()
            keys = JsonWebKey.import_key_set(jwks_data)
            self._cache[jwks_uri] = (keys, now)
            return keys
        except requests.RequestException as e:
            # If we have stale keys, use them rather than failing
            if cached:
                current_app.logger.warning(
                    f"Failed to refresh JWKS, using stale cache: {e}"
                )
                return cached[0]
            raise TokenVerificationError(f"Failed to fetch JWKS: {e}")

    def clear(self):
        """Clear all cached keys."""
        self._cache.clear()


# Global JWKS cache instance
_jwks_cache = JWKSCache()


class OIDCMetadataCache:
    """Cache for OIDC provider metadata (discovery document)."""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds

    def get_metadata(
        self, metadata_url: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get OIDC metadata from cache or fetch from provider.

        Args:
            metadata_url: URL to the .well-known/openid-configuration endpoint
            force_refresh: Force a refresh even if cache is valid

        Returns:
            OIDC metadata dictionary
        """
        now = time.time()
        cached = self._cache.get(metadata_url)

        if cached and not force_refresh:
            metadata, cached_at = cached
            if now - cached_at < self._ttl:
                return metadata

        try:
            response = requests.get(metadata_url, timeout=10)
            response.raise_for_status()
            metadata = response.json()
            self._cache[metadata_url] = (metadata, now)
            return metadata
        except requests.RequestException as e:
            if cached:
                current_app.logger.warning(
                    f"Failed to refresh OIDC metadata, using stale cache: {e}"
                )
                return cached[0]
            raise TokenVerificationError(f"Failed to fetch OIDC metadata: {e}")


# Global metadata cache instance
_metadata_cache = OIDCMetadataCache()


def get_oidc_metadata() -> Dict[str, Any]:
    """Get OIDC metadata for the configured provider."""
    metadata_url = current_app.config.get("OAUTH_METADATA_URL")
    if not metadata_url:
        raise TokenVerificationError("OAUTH_METADATA_URL not configured")
    return _metadata_cache.get_metadata(metadata_url)


def verify_token_local(
    token: str,
    verify_exp: bool = True,
    verify_aud: bool = True,
    leeway: int = 0,
) -> VerificationResult:
    """
    Verify a JWT token locally using JWKS.

    This method:
    1. Fetches the provider's public keys from the JWKS endpoint
    2. Verifies the token signature
    3. Checks standard claims (exp, iat, iss, aud)

    Args:
        token: The JWT token string
        verify_exp: Whether to verify expiration (default: True)
        verify_aud: Whether to verify audience claim (default: True)
        leeway: Seconds of leeway for expiration check (default: 0)

    Returns:
        VerificationResult with verification status and claims
    """
    try:
        # Get OIDC metadata
        metadata = get_oidc_metadata()
        jwks_uri = metadata.get("jwks_uri")
        issuer = metadata.get("issuer")

        if not jwks_uri:
            raise TokenVerificationError("jwks_uri not found in OIDC metadata")

        # Get public keys
        keys = _jwks_cache.get_keys(jwks_uri)

        # Build claims options for validation
        claims_options = {
            "iss": {"essential": True, "value": issuer},
        }

        if verify_exp:
            claims_options["exp"] = {"essential": True}

        if verify_aud:
            client_id = current_app.config.get("OAUTH_CLIENT_ID")
            if client_id:
                claims_options["aud"] = {"essential": True, "value": client_id}

        # Decode and verify the token
        try:
            claims = jwt.decode(
                token,
                keys,
                claims_options=claims_options,
            )
            claims.validate(leeway=leeway)
        except BadSignatureError:
            # Key might have rotated, try refreshing JWKS
            keys = _jwks_cache.get_keys(jwks_uri, force_refresh=True)
            claims = jwt.decode(token, keys, claims_options=claims_options)
            claims.validate(leeway=leeway)

        # Extract expiration time
        exp = claims.get("exp")
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

        return VerificationResult(
            valid=True,
            claims=dict(claims),
            method="local",
            expires_at=expires_at,
        )

    except ExpiredTokenError:
        return VerificationResult(
            valid=False,
            error="Token has expired",
            method="local",
        )
    except BadSignatureError:
        return VerificationResult(
            valid=False,
            error="Invalid token signature",
            method="local",
        )
    except InvalidClaimError as e:
        return VerificationResult(
            valid=False,
            error=f"Invalid claim: {e}",
            method="local",
        )
    except DecodeError as e:
        return VerificationResult(
            valid=False,
            error=f"Failed to decode token: {e}",
            method="local",
        )
    except TokenVerificationError as e:
        return VerificationResult(
            valid=False,
            error=str(e),
            method="local",
        )


def verify_token_introspection(token: str) -> VerificationResult:
    """
    Verify a token using the provider's introspection endpoint (RFC 7662).

    This method provides real-time token validity checking and can detect
    revoked tokens, unlike local JWT verification.

    Args:
        token: The token string (can be access_token or refresh_token)

    Returns:
        VerificationResult with verification status and claims

    Note:
        Requires client credentials (OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)
        to authenticate with the introspection endpoint.
    """
    try:
        metadata = get_oidc_metadata()
        introspection_endpoint = metadata.get("introspection_endpoint")

        if not introspection_endpoint:
            return VerificationResult(
                valid=False,
                error="Introspection endpoint not available for this provider",
                method="introspection",
            )

        client_id = current_app.config.get("OAUTH_CLIENT_ID")
        client_secret = current_app.config.get("OAUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise TokenIntrospectionError(
                "Client credentials required for token introspection"
            )

        # Call the introspection endpoint
        response = requests.post(
            introspection_endpoint,
            data={"token": token},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()

        # RFC 7662: "active" is a required boolean field
        is_active = result.get("active", False)

        if not is_active:
            return VerificationResult(
                valid=False,
                error="Token is not active (expired or revoked)",
                method="introspection",
            )

        # Extract expiration time if present
        exp = result.get("exp")
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

        return VerificationResult(
            valid=True,
            claims=result,
            method="introspection",
            expires_at=expires_at,
        )

    except requests.RequestException as e:
        return VerificationResult(
            valid=False,
            error=f"Introspection request failed: {e}",
            method="introspection",
        )
    except TokenIntrospectionError as e:
        return VerificationResult(
            valid=False,
            error=str(e),
            method="introspection",
        )


def verify_token(
    token: str,
    method: str = "auto",
    verify_exp: bool = True,
    leeway: int = 0,
) -> VerificationResult:
    """
    Verify a token using the specified method.

    Args:
        token: The token string
        method: Verification method - "local", "introspection", or "auto"
                "auto" uses local verification, falling back to introspection
                if local verification fails due to non-JWT format
        verify_exp: Whether to verify expiration (for local method)
        leeway: Seconds of leeway for expiration (for local method)

    Returns:
        VerificationResult with verification status and claims
    """
    # Check config override
    configured_method = current_app.config.get("TOKEN_VERIFICATION_METHOD", method)
    if configured_method != "auto":
        method = configured_method

    if method == "introspection":
        return verify_token_introspection(token)
    elif method == "local":
        return verify_token_local(token, verify_exp=verify_exp, leeway=leeway)
    else:  # auto
        # Try local first (faster), fall back to introspection if needed
        result = verify_token_local(token, verify_exp=verify_exp, leeway=leeway)
        if result.valid:
            return result

        # If local failed due to decode error, try introspection
        # (token might be opaque, not a JWT)
        if result.error and "decode" in result.error.lower():
            return verify_token_introspection(token)

        return result


def is_token_expiring_soon(
    token: str, threshold_seconds: int = 300
) -> Tuple[bool, Optional[datetime]]:
    """
    Check if a token will expire within the threshold.

    Useful for proactive token refresh.

    Args:
        token: The JWT token string
        threshold_seconds: How many seconds before expiration to consider
                          "expiring soon" (default: 5 minutes)

    Returns:
        Tuple of (is_expiring_soon, expiration_datetime)
    """
    result = verify_token_local(token, verify_exp=False)
    if not result.valid or not result.expires_at:
        return (True, None)  # Invalid or no expiration = treat as expiring

    threshold = datetime.now(timezone.utc) + timedelta(seconds=threshold_seconds)
    return (result.expires_at <= threshold, result.expires_at)


def require_valid_sso_token(
    method: str = "auto",
) -> Callable:
    """
    Decorator to require a valid SSO token for a route.

    Looks for the token in:
    1. Authorization header (Bearer token)
    2. Flask session (tokens.access_token)

    Args:
        method: Verification method ("local", "introspection", "auto")

    Usage:
        @app.route('/api/protected')
        @require_valid_sso_token()
        def protected_resource():
            # g.sso_claims contains the verified token claims
            return {'user': g.sso_claims.get('sub')}
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request, session

            # Skip if auth is disabled
            if not current_app.config.get("ENABLE_AUTH"):
                return fn(*args, **kwargs)

            # Try to get token from Authorization header
            token = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

            # Fall back to session token
            if not token:
                session_tokens = session.get("tokens", {})
                token = session_tokens.get("access_token")

            if not token:
                from flask import make_response

                return make_response(
                    {"message": "No SSO token provided"}, 401
                )

            # Verify the token
            result = verify_token(token, method=method)

            if not result.valid:
                from flask import make_response

                return make_response(
                    {"message": f"Invalid SSO token: {result.error}"}, 401
                )

            # Store claims in g for the request
            g.sso_claims = result.claims
            g.sso_verification_method = result.method
            g.sso_token_expires_at = result.expires_at

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def clear_caches():
    """Clear all cached JWKS and metadata. Useful for testing."""
    _jwks_cache.clear()
    _metadata_cache._cache.clear()
