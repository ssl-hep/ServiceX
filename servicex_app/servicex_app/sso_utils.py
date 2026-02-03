"""
SSO Utilities

Provides utilities for working with SSO sessions and extracting
user information from OIDC tokens across different providers.
"""

from typing import Any, Dict, List, Optional

from flask import current_app, session

from servicex_app.oidc_config import OIDCClaimMapping, get_claim_mapping


class ClaimExtractionError(Exception):
    """Error extracting required claims from token."""

    pass


def get_provider_mapping() -> OIDCClaimMapping:
    """
    Get the claim mapping for the configured OIDC provider.

    Reads OAUTH_PROVIDER from config and applies any claim overrides.

    Returns:
        OIDCClaimMapping configured for the provider
    """
    provider = current_app.config.get("OAUTH_PROVIDER", "generic")

    # Build overrides from config
    overrides = {}
    if current_app.config.get("OAUTH_ORGANIZATION_CLAIM"):
        overrides["organization"] = current_app.config["OAUTH_ORGANIZATION_CLAIM"]

    return get_claim_mapping(provider, overrides if overrides else None)


def extract_user_info(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user information from OIDC userinfo using provider-specific mappings.

    Args:
        userinfo: The userinfo dict from the OIDC provider

    Returns:
        Dict with normalized user info:
        - email: User's email address
        - name: User's display name
        - sub: Provider's subject identifier
        - organization: User's organization (if available)
        - identity_set: List of linked email addresses

    Raises:
        ClaimExtractionError: If required claims (email, sub) are missing
    """
    mapping = get_provider_mapping()

    # Extract required claims
    email = mapping.extract_email(userinfo)
    if not email:
        raise ClaimExtractionError(
            "Email claim not found in userinfo. "
            f"Expected claim path: {mapping.email}"
        )

    sub = mapping.get_claim_value(userinfo, mapping.sub)
    if not sub:
        raise ClaimExtractionError(
            "Subject (sub) claim not found in userinfo. "
            f"Expected claim path: {mapping.sub}"
        )

    # Extract optional claims
    name = mapping.extract_name(userinfo) or email
    organization = mapping.extract_organization(userinfo)
    identity_set = mapping.extract_identity_set(userinfo)

    return {
        "email": email,
        "name": name,
        "sub": sub,
        "organization": organization,
        "identity_set": identity_set,
    }


def store_session_tokens(
    tokens: Dict[str, Any], userinfo: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Store SSO tokens and user info in the Flask session.

    Args:
        tokens: Token response from OIDC provider (access_token, id_token, etc.)
        userinfo: Userinfo dict from the OIDC provider

    Returns:
        Extracted user info dict
    """
    user_info = extract_user_info(userinfo)

    # Build session tokens dict
    session_tokens = {
        "access_token": tokens["access_token"],
        "id_token": tokens.get("id_token"),
    }
    if "refresh_token" in tokens:
        session_tokens["refresh_token"] = tokens["refresh_token"]

    # Update session
    session.update(
        tokens=session_tokens,
        is_authenticated=True,
        name=user_info["name"],
        email=user_info["email"],
        institution=user_info["organization"],
        sub=user_info["sub"],
        identity_set=user_info["identity_set"],
    )

    return user_info


def get_session_user_info() -> Optional[Dict[str, Any]]:
    """
    Get user info from the current session.

    Returns:
        Dict with user info if authenticated, None otherwise
    """
    if not session.get("is_authenticated"):
        return None

    return {
        "email": session.get("email"),
        "name": session.get("name"),
        "sub": session.get("sub"),
        "organization": session.get("institution", ""),
        "identity_set": session.get("identity_set", []),
    }


def get_session_tokens() -> Optional[Dict[str, str]]:
    """
    Get SSO tokens from the current session.

    Returns:
        Dict with tokens if authenticated, None otherwise
    """
    if not session.get("is_authenticated"):
        return None

    return session.get("tokens")


def get_identity_set() -> List[str]:
    """
    Get the list of linked identities (emails) from the session.

    Returns:
        List of email addresses, or empty list if not authenticated
    """
    if not session.get("is_authenticated"):
        return []

    return session.get("identity_set", [])


def clear_session():
    """
    Clear all SSO-related keys from the session.

    Removes authentication state while preserving unrelated session data.
    """
    sso_keys = [
        "tokens",
        "is_authenticated",
        "name",
        "email",
        "institution",
        "sub",
        "identity_set",
        "user_id",
        "admin",
    ]

    for key in sso_keys:
        session.pop(key, None)


def is_session_authenticated() -> bool:
    """Check if the current session is authenticated."""
    return session.get("is_authenticated", False)


def get_session_access_token() -> Optional[str]:
    """
    Get the access token from the current session.

    Returns:
        Access token string if authenticated, None otherwise
    """
    tokens = get_session_tokens()
    return tokens.get("access_token") if tokens else None


def refresh_session_token() -> bool:
    """
    Attempt to refresh the session's access token using the refresh token.

    Returns:
        True if refresh succeeded, False otherwise

    Note:
        This requires a valid refresh_token in the session and
        the provider to support token refresh.
    """
    from servicex_app.web.utils import load_oauth_client

    tokens = get_session_tokens()
    if not tokens or "refresh_token" not in tokens:
        return False

    try:
        oauth = load_oauth_client()
        # Get OIDC metadata for token endpoint
        oauth.oauth.load_server_metadata()
        token_endpoint = oauth.oauth.server_metadata.get("token_endpoint")

        if not token_endpoint:
            return False

        from authlib.integrations.requests_client import OAuth2Session

        client = OAuth2Session(
            oauth.oauth.client_id,
            oauth.oauth.client_secret,
        )

        new_tokens = client.refresh_token(
            token_endpoint,
            refresh_token=tokens["refresh_token"],
        )

        # Update session with new tokens
        session_tokens = {
            "access_token": new_tokens["access_token"],
            "id_token": new_tokens.get("id_token", tokens.get("id_token")),
        }
        if "refresh_token" in new_tokens:
            session_tokens["refresh_token"] = new_tokens["refresh_token"]
        elif "refresh_token" in tokens:
            # Keep old refresh token if new one wasn't issued
            session_tokens["refresh_token"] = tokens["refresh_token"]

        session["tokens"] = session_tokens
        return True

    except Exception as e:
        current_app.logger.warning(f"Token refresh failed: {e}")
        return False
