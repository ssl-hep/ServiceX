"""
OIDC Provider Configuration and Claim Mapping

Supports dynamic claim extraction from any OIDC provider through
configurable claim paths. This module provides a provider-agnostic
abstraction layer for SSO integration.

Supported providers:
- Globus (with identity_set support)
- Keycloak
- Auth0
- Okta
- Azure AD / Entra ID
- AWS Cognito
- Google Identity Platform
- Generic OIDC (minimal standard claims)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class OIDCClaimMapping:
    """
    Maps provider-specific claims to ServiceX internal fields.

    Claim paths use dot notation for nested claims:
    - "email" -> token["email"]
    - "realm_access.roles" -> token["realm_access"]["roles"]
    - "https://example.com/claim" -> token["https://example.com/claim"]
    """

    # Standard OIDC claims (path in token)
    email: str = "email"
    name: str = "name"
    sub: str = "sub"

    # Optional/Provider-specific claims
    organization: Optional[str] = None
    institution: Optional[str] = None

    # Multi-identity support (e.g., Globus identity_set)
    identity_set: Optional[str] = None

    # Name composition (for providers that split names)
    given_name: Optional[str] = None
    family_name: Optional[str] = None

    def get_claim_value(self, token: Dict[str, Any], claim_path: Optional[str]) -> Any:
        """
        Extract a claim value using dot notation path.

        Args:
            token: The decoded token dictionary
            claim_path: Dot-separated path to the claim (e.g., "org.name")

        Returns:
            The claim value, or None if not found

        Examples:
            - "email" -> token["email"]
            - "org.name" -> token["org"]["name"]
            - "https://example.com/claim" -> token["https://example.com/claim"]
        """
        if not claim_path:
            return None

        # Handle URLs and other claim names with special characters
        # First, try direct lookup for claims that might contain dots (like URLs)
        if claim_path in token:
            return token[claim_path]

        # Then try dot-notation traversal
        parts = claim_path.split(".")
        value = token

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            if value is None:
                return None

        return value

    def extract_email(self, token: Dict[str, Any]) -> Optional[str]:
        """Extract email from token."""
        return self.get_claim_value(token, self.email)

    def extract_name(self, token: Dict[str, Any]) -> str:
        """
        Extract display name, composing from parts if needed.

        Falls back to composing from given_name + family_name if
        the direct name claim is not available.
        """
        name = self.get_claim_value(token, self.name)
        if name:
            return name

        # Fallback: compose from given_name + family_name
        parts = []
        if self.given_name:
            given = self.get_claim_value(token, self.given_name)
            if given:
                parts.append(given)
        if self.family_name:
            family = self.get_claim_value(token, self.family_name)
            if family:
                parts.append(family)

        return " ".join(parts) if parts else ""

    def extract_organization(self, token: Dict[str, Any]) -> str:
        """Extract organization/institution."""
        if self.organization:
            org = self.get_claim_value(token, self.organization)
            if org:
                return str(org)
        if self.institution:
            inst = self.get_claim_value(token, self.institution)
            if inst:
                return str(inst)
        return ""

    def extract_identity_set(self, token: Dict[str, Any]) -> List[str]:
        """
        Extract all linked identities (emails).

        Supports Globus-style identity_set format where each identity
        is a dict with an "email" key. Falls back to returning the
        single email if no identity_set claim is present.

        Returns:
            List of email addresses
        """
        if self.identity_set:
            identity_set = self.get_claim_value(token, self.identity_set)
            if identity_set and isinstance(identity_set, list):
                # Globus format: [{"email": "...", ...}, ...]
                emails = set()
                for identity in identity_set:
                    if isinstance(identity, dict) and "email" in identity:
                        emails.add(identity["email"])
                    elif isinstance(identity, str):
                        # Simple list of emails
                        emails.add(identity)
                if emails:
                    return list(emails)

        # Fallback: single email
        email = self.extract_email(token)
        return [email] if email else []


# Pre-configured provider mappings
PROVIDER_MAPPINGS: Dict[str, OIDCClaimMapping] = {
    "globus": OIDCClaimMapping(
        email="email",
        name="name",
        sub="sub",
        organization="organization",
        identity_set="identity_set",
    ),
    "generic": OIDCClaimMapping(
        email="email",
        name="name",
        sub="sub",
    ),
}


def get_claim_mapping(
    provider: str, overrides: Optional[Dict[str, str]] = None
) -> OIDCClaimMapping:
    """
    Get claim mapping for a provider with optional overrides.

    Args:
        provider: Provider name (globus, keycloak, auth0, okta,
                  azure_ad, cognito, google, generic)
        overrides: Dict of claim path overrides

    Returns:
        OIDCClaimMapping configured for the provider
    """
    base_mapping = PROVIDER_MAPPINGS.get(provider.lower(), PROVIDER_MAPPINGS["generic"])

    if not overrides:
        return base_mapping

    # Create new mapping with overrides
    mapping_dict = {
        "email": overrides.get("email", base_mapping.email),
        "name": overrides.get("name", base_mapping.name),
        "sub": overrides.get("sub", base_mapping.sub),
        "organization": overrides.get("organization", base_mapping.organization),
        "institution": overrides.get("institution", base_mapping.institution),
        "identity_set": overrides.get("identity_set", base_mapping.identity_set),
        "given_name": overrides.get("given_name", base_mapping.given_name),
        "family_name": overrides.get("family_name", base_mapping.family_name),
    }

    return OIDCClaimMapping(**mapping_dict)


def get_supported_providers() -> List[str]:
    """Return list of supported provider names."""
    return list(PROVIDER_MAPPINGS.keys())
