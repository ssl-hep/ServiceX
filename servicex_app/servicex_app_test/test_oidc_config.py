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
        mapping = OIDCClaimMapping(roles="realm_access.roles")
        token = {"realm_access": {"roles": ["admin", "user"]}}
        assert mapping.extract_roles(token) == ["admin", "user"]

    def test_extract_deeply_nested_claim(self):
        """Test extraction of deeply nested claim."""
        mapping = OIDCClaimMapping(roles="resource_access.client.roles")
        token = {"resource_access": {"client": {"roles": ["editor"]}}}
        assert mapping.extract_roles(token) == ["editor"]

    def test_extract_url_claim(self):
        """Test extraction of URL-style claim (Auth0 namespaced claims)."""
        mapping = OIDCClaimMapping(roles="https://example.com/roles")
        token = {"https://example.com/roles": ["admin", "user"]}
        assert mapping.extract_roles(token) == ["admin", "user"]

    def test_extract_missing_claim_returns_none(self):
        """Test that missing claims return appropriate default."""
        mapping = OIDCClaimMapping()
        token = {}
        assert mapping.extract_email(token) is None
        assert mapping.extract_organization(token) == ""
        assert mapping.extract_roles(token) == []
        assert mapping.extract_groups(token) == []

    def test_extract_missing_nested_claim(self):
        """Test extraction of missing nested claim."""
        mapping = OIDCClaimMapping(roles="realm_access.roles")
        token = {"realm_access": {}}  # roles key missing
        assert mapping.extract_roles(token) == []

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

    def test_extract_roles_list(self):
        """Test extraction of roles as list."""
        mapping = OIDCClaimMapping(roles="roles")
        token = {"roles": ["admin", "user", "editor"]}
        assert mapping.extract_roles(token) == ["admin", "user", "editor"]

    def test_extract_roles_single_string(self):
        """Test extraction of single role as string."""
        mapping = OIDCClaimMapping(roles="role")
        token = {"role": "admin"}
        assert mapping.extract_roles(token) == ["admin"]

    def test_extract_groups_list(self):
        """Test extraction of groups as list."""
        mapping = OIDCClaimMapping(groups="groups")
        token = {"groups": ["/scientists", "/admins"]}
        assert mapping.extract_groups(token) == ["/scientists", "/admins"]

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
        token = {"realm_access": "not a dict"}
        assert mapping.get_claim_value(token, "realm_access.roles") is None


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

    def test_keycloak_mapping(self):
        """Test Keycloak provider mapping."""
        mapping = get_claim_mapping("keycloak")
        assert mapping.roles == "realm_access.roles"
        assert mapping.groups == "groups"
        assert mapping.organization == "organization"
        assert mapping.given_name == "given_name"
        assert mapping.family_name == "family_name"

    def test_auth0_mapping(self):
        """Test Auth0 provider mapping."""
        mapping = get_claim_mapping("auth0")
        assert mapping.organization == "org_id"
        assert mapping.roles is None  # Must be configured via override
        assert mapping.email == "email"

    def test_okta_mapping(self):
        """Test Okta provider mapping."""
        mapping = get_claim_mapping("okta")
        assert mapping.roles == "groups"
        assert mapping.groups == "groups"
        assert mapping.organization == "organization"

    def test_azure_ad_mapping(self):
        """Test Azure AD provider mapping."""
        mapping = get_claim_mapping("azure_ad")
        assert mapping.roles == "roles"
        assert mapping.organization == "tid"
        assert mapping.groups == "groups"

    def test_cognito_mapping(self):
        """Test AWS Cognito provider mapping."""
        mapping = get_claim_mapping("cognito")
        assert mapping.roles == "cognito:groups"
        assert mapping.organization == "custom:organization"

    def test_google_mapping(self):
        """Test Google provider mapping."""
        mapping = get_claim_mapping("google")
        assert mapping.organization == "hd"  # Hosted domain
        assert mapping.given_name == "given_name"
        assert mapping.family_name == "family_name"

    def test_generic_mapping(self):
        """Test generic provider has minimal claims."""
        mapping = get_claim_mapping("generic")
        assert mapping.email == "email"
        assert mapping.name == "name"
        assert mapping.sub == "sub"
        assert mapping.roles is None
        assert mapping.groups is None
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
        mapping_lower = get_claim_mapping("keycloak")
        mapping_upper = get_claim_mapping("KEYCLOAK")
        mapping_mixed = get_claim_mapping("KeyCloak")
        assert mapping_lower.roles == mapping_upper.roles == mapping_mixed.roles

    def test_claim_override(self):
        """Test that claim overrides work."""
        mapping = get_claim_mapping("keycloak", {"roles": "custom:roles"})
        assert mapping.roles == "custom:roles"
        assert mapping.groups == "groups"  # Unchanged

    def test_multiple_overrides(self):
        """Test multiple claim overrides."""
        mapping = get_claim_mapping(
            "generic",
            {
                "roles": "my_roles",
                "groups": "my_groups",
                "organization": "company",
            },
        )
        assert mapping.roles == "my_roles"
        assert mapping.groups == "my_groups"
        assert mapping.organization == "company"
        assert mapping.email == "email"  # Unchanged

    def test_override_with_empty_dict(self):
        """Test that empty override dict doesn't change mapping."""
        mapping_no_override = get_claim_mapping("keycloak")
        mapping_empty_override = get_claim_mapping("keycloak", {})
        assert mapping_no_override.roles == mapping_empty_override.roles


class TestRealWorldTokens:
    """Test with realistic token structures from various providers."""

    def test_keycloak_token(self):
        """Test parsing a Keycloak-style token."""
        mapping = get_claim_mapping("keycloak")
        token = {
            "sub": "f:12345:user",
            "email": "user@keycloak.example.com",
            "name": "Keycloak User",
            "given_name": "Keycloak",
            "family_name": "User",
            "realm_access": {"roles": ["servicex-user", "offline_access"]},
            "resource_access": {"servicex-app": {"roles": ["editor"]}},
            "groups": ["/scientists", "/admin"],
        }

        assert mapping.extract_email(token) == "user@keycloak.example.com"
        assert mapping.extract_name(token) == "Keycloak User"
        assert "servicex-user" in mapping.extract_roles(token)
        assert "offline_access" in mapping.extract_roles(token)
        assert "/scientists" in mapping.extract_groups(token)
        assert "/admin" in mapping.extract_groups(token)

    def test_keycloak_token_with_client_roles(self):
        """Test parsing Keycloak token with client-specific roles."""
        mapping = get_claim_mapping(
            "keycloak", {"roles": "resource_access.servicex-app.roles"}
        )
        token = {
            "sub": "f:12345:user",
            "email": "user@keycloak.example.com",
            "name": "Keycloak User",
            "resource_access": {"servicex-app": {"roles": ["editor", "viewer"]}},
        }

        assert mapping.extract_roles(token) == ["editor", "viewer"]

    def test_auth0_token(self):
        """Test parsing an Auth0-style token."""
        mapping = get_claim_mapping("auth0", {"roles": "https://myapp.com/roles"})
        token = {
            "sub": "auth0|123456789",
            "email": "user@auth0.example.com",
            "name": "Auth0 User",
            "org_id": "org_abc123",
            "https://myapp.com/roles": ["admin", "user"],
        }

        assert mapping.extract_email(token) == "user@auth0.example.com"
        assert mapping.extract_name(token) == "Auth0 User"
        assert mapping.extract_organization(token) == "org_abc123"
        assert mapping.extract_roles(token) == ["admin", "user"]

    def test_azure_ad_token(self):
        """Test parsing an Azure AD-style token."""
        mapping = get_claim_mapping("azure_ad")
        token = {
            "sub": "abc-123-def",
            "email": "user@contoso.com",
            "name": "Azure User",
            "given_name": "Azure",
            "family_name": "User",
            "tid": "tenant-id-123",
            "roles": ["ServiceX.Admin"],
            "groups": ["group-id-1", "group-id-2"],
        }

        assert mapping.extract_email(token) == "user@contoso.com"
        assert mapping.extract_organization(token) == "tenant-id-123"
        assert "ServiceX.Admin" in mapping.extract_roles(token)
        assert "group-id-1" in mapping.extract_groups(token)

    def test_okta_token(self):
        """Test parsing an Okta-style token."""
        mapping = get_claim_mapping("okta")
        token = {
            "sub": "okta-user-id",
            "email": "user@okta.example.com",
            "name": "Okta User",
            "given_name": "Okta",
            "family_name": "User",
            "groups": ["ServiceX-Admins", "Scientists"],
        }

        assert mapping.extract_email(token) == "user@okta.example.com"
        assert mapping.extract_name(token) == "Okta User"
        # Okta uses groups for roles
        assert "ServiceX-Admins" in mapping.extract_roles(token)
        assert "Scientists" in mapping.extract_groups(token)

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

    def test_cognito_token(self):
        """Test parsing an AWS Cognito-style token."""
        mapping = get_claim_mapping("cognito")
        token = {
            "sub": "cognito-user-id",
            "email": "user@cognito.example.com",
            "name": "Cognito User",
            "given_name": "Cognito",
            "family_name": "User",
            "custom:organization": "AWS Labs",
            "cognito:groups": ["admins", "scientists"],
        }

        assert mapping.extract_email(token) == "user@cognito.example.com"
        assert mapping.extract_organization(token) == "AWS Labs"
        assert "admins" in mapping.extract_roles(token)
        assert "scientists" in mapping.extract_groups(token)

    def test_google_token(self):
        """Test parsing a Google-style token."""
        mapping = get_claim_mapping("google")
        token = {
            "sub": "google-user-id",
            "email": "user@company.com",
            "name": "Google User",
            "given_name": "Google",
            "family_name": "User",
            "hd": "company.com",  # Hosted domain
        }

        assert mapping.extract_email(token) == "user@company.com"
        assert mapping.extract_name(token) == "Google User"
        assert mapping.extract_organization(token) == "company.com"


class TestGetSupportedProviders:
    """Test get_supported_providers function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        providers = get_supported_providers()
        assert isinstance(providers, list)

    def test_includes_expected_providers(self):
        """Test that all expected providers are included."""
        providers = get_supported_providers()
        expected = [
            "globus",
            "keycloak",
            "auth0",
            "okta",
            "azure_ad",
            "cognito",
            "google",
            "generic",
        ]
        for provider in expected:
            assert provider in providers

    def test_matches_provider_mappings(self):
        """Test that returned providers match PROVIDER_MAPPINGS keys."""
        providers = get_supported_providers()
        assert set(providers) == set(PROVIDER_MAPPINGS.keys())
