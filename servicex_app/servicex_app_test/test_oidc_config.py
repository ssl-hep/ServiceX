"""Tests for OIDC provider configuration and claim mapping."""

import pytest

from servicex_app.oidc_config import (
    PROVIDER_MAPPINGS,
    OIDCClaimMapping,
    get_claim_mapping,
    get_supported_providers,
)


class TestOIDCClaimMapping:
    """Test OIDCClaimMapping class functionality."""

    def test_extract_simple_claim(self):
        """Test extraction of top-level claim."""
        mapping = OIDCClaimMapping()
        token = {"email": "user@example.com"}
        assert mapping.extract_email(token) == "user@example.com"

    def test_extract_nested_claim(self):
        """Test extraction of nested claim using dot notation."""
        mapping = OIDCClaimMapping(organization="org.name")
        token = {"org": {"name": "ACME Corp"}}
        assert mapping.extract_organization(token) == "ACME Corp"

    def test_extract_url_claim(self):
        """Test extraction of URL-style claim (Auth0 namespaced claims)."""
        mapping = OIDCClaimMapping(organization="https://example.com/org")
        token = {"https://example.com/org": "ACME Corp"}
        assert mapping.extract_organization(token) == "ACME Corp"

    def test_extract_missing_claim_returns_none(self):
        """Test that missing claims return appropriate default."""
        mapping = OIDCClaimMapping()
        token = {}
        assert mapping.extract_email(token) is None
        assert mapping.extract_organization(token) == ""

    def test_extract_name_direct(self):
        """Test direct name claim extraction."""
        mapping = OIDCClaimMapping(name="name")
        token = {"name": "John Doe"}
        assert mapping.extract_name(token) == "John Doe"

    def test_extract_name_composition(self):
        """Test name composition from given_name and family_name."""
        mapping = OIDCClaimMapping(
            name=None,  # No direct name claim
            given_name="given_name",
            family_name="family_name",
        )
        token = {"given_name": "John", "family_name": "Doe"}
        assert mapping.extract_name(token) == "John Doe"

    def test_extract_name_given_only(self):
        """Test name composition with only given_name."""
        mapping = OIDCClaimMapping(
            name=None,
            given_name="given_name",
            family_name="family_name",
        )
        token = {"given_name": "John"}
        assert mapping.extract_name(token) == "John"

    def test_extract_name_prefers_direct_claim(self):
        """Test that direct name claim is preferred over composition."""
        mapping = OIDCClaimMapping(
            name="name",
            given_name="given_name",
            family_name="family_name",
        )
        token = {
            "name": "Johnny Doe",
            "given_name": "John",
            "family_name": "Doe",
        }
        assert mapping.extract_name(token) == "Johnny Doe"

    def test_extract_name_empty_fallback(self):
        """Test that missing name returns empty string."""
        mapping = OIDCClaimMapping(name=None)
        token = {}
        assert mapping.extract_name(token) == ""

    def test_extract_organization_from_organization_claim(self):
        """Test organization extraction from organization claim."""
        mapping = OIDCClaimMapping(organization="organization")
        token = {"organization": "ACME Corp"}
        assert mapping.extract_organization(token) == "ACME Corp"

    def test_extract_organization_from_institution_claim(self):
        """Test organization extraction from institution claim."""
        mapping = OIDCClaimMapping(institution="institution")
        token = {"institution": "University of Science"}
        assert mapping.extract_organization(token) == "University of Science"

    def test_extract_organization_prefers_organization_claim(self):
        """Test that organization claim is preferred over institution."""
        mapping = OIDCClaimMapping(
            organization="organization",
            institution="institution",
        )
        token = {
            "organization": "ACME Corp",
            "institution": "University of Science",
        }
        assert mapping.extract_organization(token) == "ACME Corp"

    def test_globus_identity_set(self):
        """Test Globus-style identity_set extraction."""
        mapping = OIDCClaimMapping(identity_set="identity_set")
        token = {
            "email": "primary@example.com",
            "identity_set": [
                {"email": "user@globus.org", "identity_provider": "globus"},
                {"email": "user@university.edu", "identity_provider": "university"},
            ],
        }
        identities = mapping.extract_identity_set(token)
        assert len(identities) == 2
        assert "user@globus.org" in identities
        assert "user@university.edu" in identities

    def test_identity_set_simple_list(self):
        """Test identity_set with simple list of emails."""
        mapping = OIDCClaimMapping(identity_set="emails")
        token = {
            "email": "primary@example.com",
            "emails": ["user@example.com", "user@alt.com"],
        }
        identities = mapping.extract_identity_set(token)
        assert len(identities) == 2
        assert "user@example.com" in identities
        assert "user@alt.com" in identities

    def test_identity_set_fallback_to_email(self):
        """Test identity_set falls back to single email."""
        mapping = OIDCClaimMapping()  # No identity_set configured
        token = {"email": "user@example.com"}
        assert mapping.extract_identity_set(token) == ["user@example.com"]

    def test_identity_set_no_email(self):
        """Test identity_set returns empty list when no email."""
        mapping = OIDCClaimMapping()
        token = {}
        assert mapping.extract_identity_set(token) == []

    def test_get_claim_value_with_none_path(self):
        """Test get_claim_value returns None for None path."""
        mapping = OIDCClaimMapping()
        token = {"email": "user@example.com"}
        assert mapping.get_claim_value(token, None) is None

    def test_get_claim_value_traversal_through_non_dict(self):
        """Test get_claim_value handles traversal through non-dict gracefully."""
        mapping = OIDCClaimMapping()
        token = {"org": "not a dict"}
        assert mapping.get_claim_value(token, "org.name") is None


class TestProviderMappings:
    """Test pre-configured provider mappings."""

    def test_globus_mapping(self):
        """Test Globus provider mapping."""
        mapping = get_claim_mapping("globus")
        assert mapping.organization == "organization"
        assert mapping.identity_set == "identity_set"
        assert mapping.email == "email"
        assert mapping.name == "name"
        assert mapping.sub == "sub"

    def test_generic_mapping(self):
        """Test generic provider has minimal claims."""
        mapping = get_claim_mapping("generic")
        assert mapping.email == "email"
        assert mapping.name == "name"
        assert mapping.sub == "sub"
        assert mapping.organization is None

    def test_unknown_provider_uses_generic(self):
        """Test unknown provider falls back to generic."""
        mapping = get_claim_mapping("unknown_provider")
        generic = PROVIDER_MAPPINGS["generic"]
        assert mapping.email == generic.email
        assert mapping.name == generic.name
        assert mapping.sub == generic.sub

    def test_case_insensitive_provider_name(self):
        """Test provider name is case-insensitive."""
        mapping_lower = get_claim_mapping("globus")
        mapping_upper = get_claim_mapping("GLOBUS")
        mapping_mixed = get_claim_mapping("Globus")
        assert (
            mapping_lower.organization
            == mapping_upper.organization
            == mapping_mixed.organization
        )

    def test_claim_override(self):
        """Test that claim overrides work."""
        mapping = get_claim_mapping("generic", {"organization": "custom_org"})
        assert mapping.organization == "custom_org"
        assert mapping.email == "email"  # Unchanged

    def test_multiple_overrides(self):
        """Test multiple claim overrides."""
        mapping = get_claim_mapping(
            "generic",
            {
                "organization": "company",
                "identity_set": "linked_emails",
            },
        )
        assert mapping.organization == "company"
        assert mapping.identity_set == "linked_emails"
        assert mapping.email == "email"  # Unchanged

    def test_override_with_empty_dict(self):
        """Test that empty override dict doesn't change mapping."""
        mapping_no_override = get_claim_mapping("globus")
        mapping_empty_override = get_claim_mapping("globus", {})
        assert mapping_no_override.organization == mapping_empty_override.organization


class TestRealWorldTokens:
    """Test with realistic token structures from various providers."""

    def test_globus_token(self):
        """Test parsing a Globus-style token."""
        mapping = get_claim_mapping("globus")
        token = {
            "sub": "globus-user-id",
            "email": "primary@university.edu",
            "name": "Globus User",
            "organization": "University of Science",
            "identity_set": [
                {"email": "primary@university.edu", "identity_provider": "university"},
                {"email": "user@gmail.com", "identity_provider": "google"},
            ],
        }

        assert mapping.extract_email(token) == "primary@university.edu"
        assert mapping.extract_name(token) == "Globus User"
        assert mapping.extract_organization(token) == "University of Science"
        identities = mapping.extract_identity_set(token)
        assert len(identities) == 2
        assert "primary@university.edu" in identities
        assert "user@gmail.com" in identities

    def test_generic_token(self):
        """Test parsing a generic OIDC token."""
        mapping = get_claim_mapping("generic")
        token = {
            "sub": "user-id-123",
            "email": "user@example.com",
            "name": "Generic User",
        }

        assert mapping.extract_email(token) == "user@example.com"
        assert mapping.extract_name(token) == "Generic User"
        assert mapping.get_claim_value(token, mapping.sub) == "user-id-123"


class TestGetSupportedProviders:
    """Test get_supported_providers function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        providers = get_supported_providers()
        assert isinstance(providers, list)

    def test_includes_expected_providers(self):
        """Test that expected providers are included."""
        providers = get_supported_providers()
        assert "globus" in providers
        assert "generic" in providers

    def test_matches_provider_mappings(self):
        """Test that returned providers match PROVIDER_MAPPINGS keys."""
        providers = get_supported_providers()
        assert set(providers) == set(PROVIDER_MAPPINGS.keys())
