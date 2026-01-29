"""
Generic SSO Utilities

Provider-agnostic utilities for SSO integration, built on top of authlib.
This module provides claim extraction and session management that works
with any OIDC provider.

Authlib handles:
- Token exchange and validation
- JWKS fetching and caching
- ID token parsing (available as token['userinfo'])

This module adds:
- Provider-specific claim path mapping
- Normalized user info extraction
- Role/group checking utilities
- Session management helpers
"""
from typing import Any, Dict, List, Optional

from flask import current_app, session

from servicex_app.oidc_config import OIDCClaimMapping, get_claim_mapping

import logging

logger = logging.getLogger(__name__)


class SSOError(Exception):
    """Base exception for SSO operations."""

    pass


class ClaimExtractionError(SSOError):
    """Failed to extract required claim."""

    pass


def get_provider_mapping() -> OIDCClaimMapping:
    """
    Get the configured claim mapping for the current provider.

    Reads the OAUTH_PROVIDER config and any claim overrides from
    OAUTH_*_CLAIM configuration variables.

    Returns:
        OIDCClaimMapping configured for the current provider
    """
    provider = current_app.config.get("OAUTH_PROVIDER", "generic")

    # Build overrides from config
    config_to_claim = {
        "OAUTH_EMAIL_CLAIM": "email",
        "OAUTH_NAME_CLAIM": "name",
        "OAUTH_SUB_CLAIM": "sub",
        "OAUTH_ORGANIZATION_CLAIM": "organization",
        "OAUTH_INSTITUTION_CLAIM": "institution",
        "OAUTH_GROUPS_CLAIM": "groups",
        "OAUTH_ROLES_CLAIM": "roles",
        "OAUTH_IDENTITY_SET_CLAIM": "identity_set",
        "OAUTH_GIVEN_NAME_CLAIM": "given_name",
        "OAUTH_FAMILY_NAME_CLAIM": "family_name",
    }

    overrides = {}
    for config_key, mapping_key in config_to_claim.items():
        value = current_app.config.get(config_key)
        if value:
            overrides[mapping_key] = value

    return get_claim_mapping(provider, overrides if overrides else None)


def extract_user_info(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract normalized user information from authlib's userinfo.

    Uses the configured provider mapping to extract claims
    in a provider-agnostic way. The userinfo dict comes from
    authlib's token['userinfo'] after authorize_access_token().

    Args:
        userinfo: The userinfo dict from authlib (token['userinfo'])

    Returns:
        Normalized user info dict with keys:
        - email: str
        - name: str
        - sub: str
        - organization: str
        - identity_set: List[str]
        - roles: List[str]
        - groups: List[str]

    Raises:
        ClaimExtractionError: If required claims are missing
    """
    mapping = get_provider_mapping()

    email = mapping.extract_email(userinfo)
    if not email:
        raise ClaimExtractionError("Email claim not found in token")

    sub = mapping.get_claim_value(userinfo, mapping.sub)
    if not sub:
        raise ClaimExtractionError("Subject (sub) claim not found in token")

    return {
        "email": email,
        "name": mapping.extract_name(userinfo) or email,
        "sub": sub,
        "organization": mapping.extract_organization(userinfo),
        "identity_set": mapping.extract_identity_set(userinfo),
        "roles": mapping.extract_roles(userinfo),
        "groups": mapping.extract_groups(userinfo),
    }


def store_session_tokens(
    tokens: Dict[str, Any], userinfo: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Store OAuth tokens and user info in Flask session.

    Extracts user information using the configured provider mapping
    and stores everything in the Flask session.

    Args:
        tokens: The token dict from authlib's authorize_access_token()
                Contains access_token, id_token, and optionally refresh_token
        userinfo: The userinfo dict (typically tokens['userinfo'])

    Returns:
        The extracted user info dict
    """
    user_info = extract_user_info(userinfo)

    session_tokens = {
        "access_token": tokens["access_token"],
        "id_token": tokens.get("id_token"),
    }

    if "refresh_token" in tokens:
        session_tokens["refresh_token"] = tokens["refresh_token"]

    session.update(
        tokens=session_tokens,
        is_authenticated=True,
        name=user_info["name"],
        email=user_info["email"],
        institution=user_info["organization"],
        sub=user_info["sub"],
        identity_set=user_info["identity_set"],
        roles=user_info["roles"],
        groups=user_info["groups"],
    )

    return user_info


def get_session_user_info() -> Optional[Dict[str, Any]]:
    """
    Get user info from current session.

    Returns:
        User info dict or None if not authenticated
    """
    if not session.get("is_authenticated"):
        return None

    return {
        "email": session.get("email"),
        "name": session.get("name"),
        "sub": session.get("sub"),
        "organization": session.get("institution"),
        "identity_set": session.get("identity_set", []),
        "roles": session.get("roles", []),
        "groups": session.get("groups", []),
    }


def get_session_tokens() -> Optional[Dict[str, str]]:
    """
    Get OAuth tokens from current session.

    Returns:
        Dict with access_token, id_token, and optionally refresh_token,
        or None if not authenticated
    """
    if not session.get("is_authenticated"):
        return None

    return session.get("tokens")


def has_role(required_role: str) -> bool:
    """
    Check if current user has a specific role.

    Args:
        required_role: The role name to check for

    Returns:
        True if user has the role, False otherwise
    """
    user_info = get_session_user_info()
    if not user_info:
        return False
    return required_role in user_info.get("roles", [])


def has_any_role(*required_roles: str) -> bool:
    """
    Check if current user has any of the required roles.

    Args:
        *required_roles: Role names (any one is sufficient)

    Returns:
        True if user has at least one of the roles
    """
    user_info = get_session_user_info()
    if not user_info:
        return False
    user_roles = set(user_info.get("roles", []))
    return bool(user_roles.intersection(required_roles))


def has_all_roles(*required_roles: str) -> bool:
    """
    Check if current user has all of the required roles.

    Args:
        *required_roles: Role names (all are required)

    Returns:
        True if user has all of the specified roles
    """
    user_info = get_session_user_info()
    if not user_info:
        return False
    user_roles = set(user_info.get("roles", []))
    return all(role in user_roles for role in required_roles)


def is_in_group(required_group: str) -> bool:
    """
    Check if current user is in a specific group.

    Args:
        required_group: The group name to check for

    Returns:
        True if user is in the group, False otherwise
    """
    user_info = get_session_user_info()
    if not user_info:
        return False
    return required_group in user_info.get("groups", [])


def is_in_any_group(*required_groups: str) -> bool:
    """
    Check if current user is in any of the required groups.

    Args:
        *required_groups: Group names (any one is sufficient)

    Returns:
        True if user is in at least one of the groups
    """
    user_info = get_session_user_info()
    if not user_info:
        return False
    user_groups = set(user_info.get("groups", []))
    return bool(user_groups.intersection(required_groups))


def clear_session() -> None:
    """
    Clear all SSO-related data from session.

    Called during logout to ensure clean state.
    """
    keys_to_clear = [
        "tokens",
        "is_authenticated",
        "name",
        "email",
        "institution",
        "sub",
        "identity_set",
        "roles",
        "groups",
        "user_id",
        "admin",
    ]

    for key in keys_to_clear:
        session.pop(key, None)


def get_identity_set() -> List[str]:
    """
    Get the identity set (linked emails) for the current user.

    Returns:
        List of email addresses linked to this user
    """
    user_info = get_session_user_info()
    if not user_info:
        return []
    return user_info.get("identity_set", [])
