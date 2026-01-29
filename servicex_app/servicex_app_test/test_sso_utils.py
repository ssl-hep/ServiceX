"""Tests for SSO utilities."""
from unittest.mock import MagicMock, patch

import pytest

from servicex_app.oidc_config import OIDCClaimMapping


class TestExtractUserInfo:
    """Tests for user info extraction."""

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_minimal(self, mock_mapping):
        """Test extraction with minimal claims."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping()

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
        }

        user_info = extract_user_info(userinfo)

        assert user_info["email"] == "user@example.com"
        assert user_info["name"] == "Test User"
        assert user_info["sub"] == "user-123"
        assert user_info["organization"] == ""
        assert user_info["roles"] == []
        assert user_info["groups"] == []

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_with_roles(self, mock_mapping):
        """Test extraction with roles."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping(roles="roles")

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "roles": ["admin", "user"],
        }

        user_info = extract_user_info(userinfo)

        assert user_info["roles"] == ["admin", "user"]

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_with_groups(self, mock_mapping):
        """Test extraction with groups."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping(groups="groups")

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "groups": ["/scientists", "/admins"],
        }

        user_info = extract_user_info(userinfo)

        assert user_info["groups"] == ["/scientists", "/admins"]

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_with_organization(self, mock_mapping):
        """Test extraction with organization."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping(organization="organization")

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "organization": "ACME Corp",
        }

        user_info = extract_user_info(userinfo)

        assert user_info["organization"] == "ACME Corp"

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_with_identity_set(self, mock_mapping):
        """Test extraction with identity set (Globus-style)."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping(identity_set="identity_set")

        userinfo = {
            "sub": "user-123",
            "email": "primary@example.com",
            "name": "Test User",
            "identity_set": [
                {"email": "primary@example.com"},
                {"email": "secondary@example.com"},
            ],
        }

        user_info = extract_user_info(userinfo)

        assert len(user_info["identity_set"]) == 2
        assert "primary@example.com" in user_info["identity_set"]
        assert "secondary@example.com" in user_info["identity_set"]

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_keycloak_roles(self, mock_mapping):
        """Test extraction with Keycloak nested roles."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping(roles="realm_access.roles")

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "realm_access": {"roles": ["servicex-admin", "offline_access"]},
        }

        user_info = extract_user_info(userinfo)

        assert "servicex-admin" in user_info["roles"]
        assert "offline_access" in user_info["roles"]

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_missing_email_raises(self, mock_mapping):
        """Test that missing email raises error."""
        from servicex_app.sso_utils import ClaimExtractionError, extract_user_info

        mock_mapping.return_value = OIDCClaimMapping()

        userinfo = {"sub": "user-123", "name": "No Email User"}

        with pytest.raises(ClaimExtractionError, match="Email claim not found"):
            extract_user_info(userinfo)

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_missing_sub_raises(self, mock_mapping):
        """Test that missing sub raises error."""
        from servicex_app.sso_utils import ClaimExtractionError, extract_user_info

        mock_mapping.return_value = OIDCClaimMapping()

        userinfo = {"email": "user@example.com", "name": "No Sub User"}

        with pytest.raises(ClaimExtractionError, match="Subject"):
            extract_user_info(userinfo)

    @patch("servicex_app.sso_utils.get_provider_mapping")
    def test_extract_user_info_name_fallback_to_email(self, mock_mapping):
        """Test that name falls back to email if not present."""
        from servicex_app.sso_utils import extract_user_info

        mock_mapping.return_value = OIDCClaimMapping()

        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            # No name claim
        }

        user_info = extract_user_info(userinfo)

        assert user_info["name"] == "user@example.com"


class TestRoleChecks:
    """Tests for role checking functions."""

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_role_true(self, mock_user_info):
        """Test has_role returns True when user has role."""
        from servicex_app.sso_utils import has_role

        mock_user_info.return_value = {"roles": ["admin", "user"]}
        assert has_role("admin") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_role_false(self, mock_user_info):
        """Test has_role returns False when user lacks role."""
        from servicex_app.sso_utils import has_role

        mock_user_info.return_value = {"roles": ["user"]}
        assert has_role("admin") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_role_no_session(self, mock_user_info):
        """Test has_role returns False when not authenticated."""
        from servicex_app.sso_utils import has_role

        mock_user_info.return_value = None
        assert has_role("admin") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_role_empty_roles(self, mock_user_info):
        """Test has_role returns False when roles list is empty."""
        from servicex_app.sso_utils import has_role

        mock_user_info.return_value = {"roles": []}
        assert has_role("admin") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_any_role_one_match(self, mock_user_info):
        """Test has_any_role with one matching role."""
        from servicex_app.sso_utils import has_any_role

        mock_user_info.return_value = {"roles": ["editor"]}
        assert has_any_role("admin", "editor", "viewer") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_any_role_multiple_matches(self, mock_user_info):
        """Test has_any_role with multiple matching roles."""
        from servicex_app.sso_utils import has_any_role

        mock_user_info.return_value = {"roles": ["admin", "editor"]}
        assert has_any_role("admin", "editor", "viewer") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_any_role_no_match(self, mock_user_info):
        """Test has_any_role with no matching roles."""
        from servicex_app.sso_utils import has_any_role

        mock_user_info.return_value = {"roles": ["editor"]}
        assert has_any_role("admin", "superuser") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_any_role_no_session(self, mock_user_info):
        """Test has_any_role returns False when not authenticated."""
        from servicex_app.sso_utils import has_any_role

        mock_user_info.return_value = None
        assert has_any_role("admin") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_all_roles_success(self, mock_user_info):
        """Test has_all_roles when user has all roles."""
        from servicex_app.sso_utils import has_all_roles

        mock_user_info.return_value = {"roles": ["admin", "user", "editor"]}
        assert has_all_roles("admin", "user") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_all_roles_missing_one(self, mock_user_info):
        """Test has_all_roles when user is missing one role."""
        from servicex_app.sso_utils import has_all_roles

        mock_user_info.return_value = {"roles": ["admin", "user"]}
        assert has_all_roles("admin", "superuser") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_has_all_roles_no_session(self, mock_user_info):
        """Test has_all_roles returns False when not authenticated."""
        from servicex_app.sso_utils import has_all_roles

        mock_user_info.return_value = None
        assert has_all_roles("admin") is False


class TestGroupChecks:
    """Tests for group checking functions."""

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_group_true(self, mock_user_info):
        """Test is_in_group returns True when user is in group."""
        from servicex_app.sso_utils import is_in_group

        mock_user_info.return_value = {"groups": ["/scientists", "/admins"]}
        assert is_in_group("/scientists") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_group_false(self, mock_user_info):
        """Test is_in_group returns False when user is not in group."""
        from servicex_app.sso_utils import is_in_group

        mock_user_info.return_value = {"groups": ["/scientists"]}
        assert is_in_group("/admins") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_group_no_session(self, mock_user_info):
        """Test is_in_group returns False when not authenticated."""
        from servicex_app.sso_utils import is_in_group

        mock_user_info.return_value = None
        assert is_in_group("/scientists") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_any_group_one_match(self, mock_user_info):
        """Test is_in_any_group with one matching group."""
        from servicex_app.sso_utils import is_in_any_group

        mock_user_info.return_value = {"groups": ["/scientists"]}
        assert is_in_any_group("/admins", "/scientists") is True

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_any_group_no_match(self, mock_user_info):
        """Test is_in_any_group with no matching groups."""
        from servicex_app.sso_utils import is_in_any_group

        mock_user_info.return_value = {"groups": ["/users"]}
        assert is_in_any_group("/admins", "/scientists") is False

    @patch("servicex_app.sso_utils.get_session_user_info")
    def test_is_in_any_group_no_session(self, mock_user_info):
        """Test is_in_any_group returns False when not authenticated."""
        from servicex_app.sso_utils import is_in_any_group

        mock_user_info.return_value = None
        assert is_in_any_group("/admins") is False


class TestSessionFunctions:
    """Tests for session management functions."""

    @patch("servicex_app.sso_utils.session", {"is_authenticated": False})
    def test_get_session_user_info_not_authenticated(self):
        """Test get_session_user_info when not authenticated."""
        from servicex_app.sso_utils import get_session_user_info

        result = get_session_user_info()
        assert result is None

    @patch(
        "servicex_app.sso_utils.session",
        {
            "is_authenticated": True,
            "email": "user@example.com",
            "name": "Test User",
            "sub": "user-123",
            "institution": "ACME Corp",
            "identity_set": ["user@example.com"],
            "roles": ["admin"],
            "groups": ["/scientists"],
        },
    )
    def test_get_session_user_info_authenticated(self):
        """Test get_session_user_info when authenticated."""
        from servicex_app.sso_utils import get_session_user_info

        result = get_session_user_info()

        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["name"] == "Test User"
        assert result["sub"] == "user-123"
        assert result["organization"] == "ACME Corp"
        assert result["identity_set"] == ["user@example.com"]
        assert result["roles"] == ["admin"]
        assert result["groups"] == ["/scientists"]

    @patch("servicex_app.sso_utils.session", {"is_authenticated": False})
    def test_get_session_tokens_not_authenticated(self):
        """Test get_session_tokens when not authenticated."""
        from servicex_app.sso_utils import get_session_tokens

        result = get_session_tokens()
        assert result is None

    @patch(
        "servicex_app.sso_utils.session",
        {
            "is_authenticated": True,
            "tokens": {
                "access_token": "access-token-123",
                "id_token": "id-token-456",
                "refresh_token": "refresh-token-789",
            },
        },
    )
    def test_get_session_tokens_authenticated(self):
        """Test get_session_tokens when authenticated."""
        from servicex_app.sso_utils import get_session_tokens

        result = get_session_tokens()

        assert result is not None
        assert result["access_token"] == "access-token-123"
        assert result["id_token"] == "id-token-456"
        assert result["refresh_token"] == "refresh-token-789"

    @patch(
        "servicex_app.sso_utils.session",
        {
            "is_authenticated": True,
            "identity_set": ["user@example.com", "user@alt.com"],
        },
    )
    def test_get_identity_set(self):
        """Test get_identity_set returns linked emails."""
        from servicex_app.sso_utils import get_identity_set

        result = get_identity_set()

        assert len(result) == 2
        assert "user@example.com" in result
        assert "user@alt.com" in result

    @patch("servicex_app.sso_utils.session", {"is_authenticated": False})
    def test_get_identity_set_not_authenticated(self):
        """Test get_identity_set when not authenticated."""
        from servicex_app.sso_utils import get_identity_set

        result = get_identity_set()
        assert result == []


class TestClearSession:
    """Tests for clear_session function."""

    def test_clear_session(self):
        """Test that clear_session removes all SSO keys."""
        from servicex_app.sso_utils import clear_session

        mock_session = {
            "tokens": {"access_token": "token"},
            "is_authenticated": True,
            "name": "Test User",
            "email": "user@example.com",
            "institution": "ACME",
            "sub": "user-123",
            "identity_set": ["user@example.com"],
            "roles": ["admin"],
            "groups": ["/scientists"],
            "user_id": 1,
            "admin": True,
            "unrelated_key": "should remain",
        }

        with patch("servicex_app.sso_utils.session", mock_session):
            clear_session()

            # SSO keys should be removed
            assert "tokens" not in mock_session
            assert "is_authenticated" not in mock_session
            assert "name" not in mock_session
            assert "email" not in mock_session
            assert "institution" not in mock_session
            assert "sub" not in mock_session
            assert "identity_set" not in mock_session
            assert "roles" not in mock_session
            assert "groups" not in mock_session
            assert "user_id" not in mock_session
            assert "admin" not in mock_session

            # Unrelated key should remain
            assert mock_session.get("unrelated_key") == "should remain"


class TestStoreSessionTokens:
    """Tests for store_session_tokens function."""

    @patch("servicex_app.sso_utils.get_provider_mapping")
    @patch("servicex_app.sso_utils.session", {})
    def test_store_session_tokens_basic(self, mock_mapping):
        """Test storing tokens in session."""
        from servicex_app.sso_utils import session, store_session_tokens

        mock_mapping.return_value = OIDCClaimMapping()

        tokens = {
            "access_token": "access-123",
            "id_token": "id-456",
        }
        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
        }

        result = store_session_tokens(tokens, userinfo)

        assert session["is_authenticated"] is True
        assert session["email"] == "user@example.com"
        assert session["name"] == "Test User"
        assert session["sub"] == "user-123"
        assert session["tokens"]["access_token"] == "access-123"
        assert session["tokens"]["id_token"] == "id-456"

        # Check returned user_info
        assert result["email"] == "user@example.com"
        assert result["name"] == "Test User"

    @patch("servicex_app.sso_utils.get_provider_mapping")
    @patch("servicex_app.sso_utils.session", {})
    def test_store_session_tokens_with_refresh(self, mock_mapping):
        """Test storing tokens including refresh token."""
        from servicex_app.sso_utils import session, store_session_tokens

        mock_mapping.return_value = OIDCClaimMapping()

        tokens = {
            "access_token": "access-123",
            "id_token": "id-456",
            "refresh_token": "refresh-789",
        }
        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
        }

        store_session_tokens(tokens, userinfo)

        assert session["tokens"]["refresh_token"] == "refresh-789"

    @patch("servicex_app.sso_utils.get_provider_mapping")
    @patch("servicex_app.sso_utils.session", {})
    def test_store_session_tokens_with_roles_and_groups(self, mock_mapping):
        """Test storing tokens with roles and groups."""
        from servicex_app.sso_utils import session, store_session_tokens

        mock_mapping.return_value = OIDCClaimMapping(roles="roles", groups="groups")

        tokens = {
            "access_token": "access-123",
            "id_token": "id-456",
        }
        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "roles": ["admin", "user"],
            "groups": ["/scientists"],
        }

        store_session_tokens(tokens, userinfo)

        assert session["roles"] == ["admin", "user"]
        assert session["groups"] == ["/scientists"]

    @patch("servicex_app.sso_utils.get_provider_mapping")
    @patch("servicex_app.sso_utils.session", {})
    def test_store_session_tokens_keycloak_style(self, mock_mapping):
        """Test storing tokens with Keycloak-style nested claims."""
        from servicex_app.sso_utils import session, store_session_tokens

        mock_mapping.return_value = OIDCClaimMapping(
            roles="realm_access.roles", groups="groups"
        )

        tokens = {
            "access_token": "access-123",
            "id_token": "id-456",
        }
        userinfo = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Test User",
            "realm_access": {"roles": ["servicex-admin", "offline_access"]},
            "groups": ["/atlas", "/cms"],
        }

        store_session_tokens(tokens, userinfo)

        assert "servicex-admin" in session["roles"]
        assert "offline_access" in session["roles"]
        assert "/atlas" in session["groups"]


class TestGetProviderMapping:
    """Tests for get_provider_mapping function."""

    def test_get_provider_mapping_default(self):
        """Test get_provider_mapping with default (generic) provider."""
        mock_app = MagicMock()
        mock_app.config = {}

        with patch("servicex_app.sso_utils.current_app", mock_app):
            from servicex_app.sso_utils import get_provider_mapping

            mapping = get_provider_mapping()

            assert mapping.email == "email"
            assert mapping.name == "name"
            assert mapping.sub == "sub"

    def test_get_provider_mapping_keycloak(self):
        """Test get_provider_mapping with Keycloak provider."""
        mock_app = MagicMock()
        mock_app.config = {"OAUTH_PROVIDER": "keycloak"}

        with patch("servicex_app.sso_utils.current_app", mock_app):
            from servicex_app.sso_utils import get_provider_mapping

            mapping = get_provider_mapping()

            assert mapping.roles == "realm_access.roles"
            assert mapping.groups == "groups"

    def test_get_provider_mapping_globus(self):
        """Test get_provider_mapping with Globus provider."""
        mock_app = MagicMock()
        mock_app.config = {"OAUTH_PROVIDER": "globus"}

        with patch("servicex_app.sso_utils.current_app", mock_app):
            from servicex_app.sso_utils import get_provider_mapping

            mapping = get_provider_mapping()

            assert mapping.organization == "organization"
            assert mapping.identity_set == "identity_set"

    def test_get_provider_mapping_with_overrides(self):
        """Test get_provider_mapping with config overrides."""
        mock_app = MagicMock()
        mock_app.config = {
            "OAUTH_PROVIDER": "keycloak",
            "OAUTH_ROLES_CLAIM": "custom:roles",
            "OAUTH_ORGANIZATION_CLAIM": "custom:org",
        }

        with patch("servicex_app.sso_utils.current_app", mock_app):
            from servicex_app.sso_utils import get_provider_mapping

            mapping = get_provider_mapping()

            assert mapping.roles == "custom:roles"
            assert mapping.organization == "custom:org"
            # Other Keycloak defaults should still apply
            assert mapping.groups == "groups"
