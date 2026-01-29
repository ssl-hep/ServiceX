"""Tests for RBAC decorators (role_required, group_required)."""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config["ENABLE_AUTH"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


class TestRoleRequired:
    """Tests for @role_required decorator."""

    def test_role_required_auth_disabled(self, app):
        """Test that decorator passes through when auth is disabled."""
        from servicex_app.decorators import role_required

        app.config["ENABLE_AUTH"] = False

        @role_required("admin")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            assert result["status"] == "ok"

    @patch("servicex_app.decorators.session", {"is_authenticated": False})
    def test_role_required_not_authenticated(self, app):
        """Test that decorator returns 401 when not authenticated."""
        from servicex_app.decorators import role_required

        @role_required("admin")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            assert response.status_code == 401
            assert b"Authentication required" in response.data

    @patch("servicex_app.decorators.has_any_role")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_required_has_role(self, mock_has_any_role, app):
        """Test that decorator allows access when user has required role."""
        from servicex_app.decorators import role_required

        mock_has_any_role.return_value = True

        @role_required("admin")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            mock_has_any_role.assert_called_once_with("admin")

    @patch("servicex_app.decorators.has_any_role")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_required_missing_role(self, mock_has_any_role, app):
        """Test that decorator returns 403 when user lacks required role."""
        from servicex_app.decorators import role_required

        mock_has_any_role.return_value = False

        @role_required("admin")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            assert response.status_code == 403
            assert b"Requires one of" in response.data
            assert b"admin" in response.data

    @patch("servicex_app.decorators.has_any_role")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_required_multiple_roles_any(self, mock_has_any_role, app):
        """Test decorator with multiple roles (any one sufficient)."""
        from servicex_app.decorators import role_required

        mock_has_any_role.return_value = True

        @role_required("admin", "editor", "viewer")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            mock_has_any_role.assert_called_once_with("admin", "editor", "viewer")

    @patch("servicex_app.decorators.has_all_roles")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_required_multiple_roles_all(self, mock_has_all_roles, app):
        """Test decorator with multiple roles (all required)."""
        from servicex_app.decorators import role_required

        mock_has_all_roles.return_value = True

        @role_required("admin", "editor", require_all=True)
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            mock_has_all_roles.assert_called_once_with("admin", "editor")

    @patch("servicex_app.decorators.has_all_roles")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_required_multiple_roles_all_missing(self, mock_has_all_roles, app):
        """Test decorator returns 403 when missing one of required roles."""
        from servicex_app.decorators import role_required

        mock_has_all_roles.return_value = False

        @role_required("admin", "superuser", require_all=True)
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            assert response.status_code == 403
            assert b"Requires all roles" in response.data


class TestGroupRequired:
    """Tests for @group_required decorator."""

    def test_group_required_auth_disabled(self, app):
        """Test that decorator passes through when auth is disabled."""
        from servicex_app.decorators import group_required

        app.config["ENABLE_AUTH"] = False

        @group_required("/scientists")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            assert result["status"] == "ok"

    @patch("servicex_app.decorators.session", {"is_authenticated": False})
    def test_group_required_not_authenticated(self, app):
        """Test that decorator returns 401 when not authenticated."""
        from servicex_app.decorators import group_required

        @group_required("/scientists")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            assert response.status_code == 401
            assert b"Authentication required" in response.data

    @patch("servicex_app.decorators.is_in_any_group")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_group_required_in_group(self, mock_is_in_any_group, app):
        """Test that decorator allows access when user is in required group."""
        from servicex_app.decorators import group_required

        mock_is_in_any_group.return_value = True

        @group_required("/scientists")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            mock_is_in_any_group.assert_called_once_with("/scientists")

    @patch("servicex_app.decorators.is_in_any_group")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_group_required_not_in_group(self, mock_is_in_any_group, app):
        """Test that decorator returns 403 when user is not in required group."""
        from servicex_app.decorators import group_required

        mock_is_in_any_group.return_value = False

        @group_required("/admins")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            assert response.status_code == 403
            assert b"Requires membership in" in response.data
            assert b"/admins" in response.data

    @patch("servicex_app.decorators.is_in_any_group")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_group_required_multiple_groups(self, mock_is_in_any_group, app):
        """Test decorator with multiple groups (any one sufficient)."""
        from servicex_app.decorators import group_required

        mock_is_in_any_group.return_value = True

        @group_required("/atlas", "/cms", "/lhcb")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200
            mock_is_in_any_group.assert_called_once_with("/atlas", "/cms", "/lhcb")


class TestAdminRequiredWithSSORole:
    """Tests for @admin_required with SSO admin role support."""

    @patch("servicex_app.decorators.has_any_role")
    @patch(
        "servicex_app.decorators.session",
        {"is_authenticated": True, "admin": False},
    )
    def test_admin_required_sso_role(self, mock_has_any_role, app):
        """Test that admin_required checks SSO admin role."""
        from servicex_app.decorators import admin_required

        app.config["OAUTH_ADMIN_ROLE"] = "servicex-admin"
        mock_has_any_role.return_value = True

        @admin_required
        def admin_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = admin_view()
            assert status == 200
            mock_has_any_role.assert_called_once_with("servicex-admin")

    @patch("servicex_app.decorators.has_any_role")
    @patch(
        "servicex_app.decorators.session",
        {"is_authenticated": True, "admin": False},
    )
    def test_admin_required_no_sso_role_configured(self, mock_has_any_role, app):
        """Test admin_required without SSO admin role configured."""
        from servicex_app.decorators import admin_required

        # No OAUTH_ADMIN_ROLE configured
        app.config.pop("OAUTH_ADMIN_ROLE", None)

        @admin_required
        def admin_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = admin_view()
            assert response.status_code == 401
            # has_any_role should not be called when no role configured
            mock_has_any_role.assert_not_called()

    @patch(
        "servicex_app.decorators.session",
        {"is_authenticated": True, "admin": True},
    )
    def test_admin_required_db_admin_takes_precedence(self, app):
        """Test that database admin flag is checked first."""
        from servicex_app.decorators import admin_required

        app.config["OAUTH_ADMIN_ROLE"] = "servicex-admin"

        @admin_required
        def admin_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = admin_view()
            assert status == 200

    @patch("servicex_app.decorators.has_any_role")
    @patch(
        "servicex_app.decorators.session",
        {"is_authenticated": True, "admin": False},
    )
    def test_admin_required_sso_role_missing(self, mock_has_any_role, app):
        """Test admin_required returns 401 when SSO admin role is missing."""
        from servicex_app.decorators import admin_required

        app.config["OAUTH_ADMIN_ROLE"] = "servicex-admin"
        mock_has_any_role.return_value = False

        @admin_required
        def admin_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = admin_view()
            assert response.status_code == 401
            assert b"restricted to administrators" in response.data


class TestDecoratorCombinations:
    """Tests for combining decorators."""

    @patch("servicex_app.decorators.has_any_role")
    @patch("servicex_app.decorators.is_in_any_group")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_and_group_required(
        self, mock_is_in_any_group, mock_has_any_role, app
    ):
        """Test combining role and group decorators."""
        from servicex_app.decorators import group_required, role_required

        mock_has_any_role.return_value = True
        mock_is_in_any_group.return_value = True

        @role_required("scientist")
        @group_required("/atlas")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            result, status = protected_view()
            assert status == 200

    @patch("servicex_app.decorators.has_any_role")
    @patch("servicex_app.decorators.is_in_any_group")
    @patch("servicex_app.decorators.session", {"is_authenticated": True})
    def test_role_passes_group_fails(
        self, mock_is_in_any_group, mock_has_any_role, app
    ):
        """Test that inner decorator failure is returned."""
        from servicex_app.decorators import group_required, role_required

        mock_has_any_role.return_value = True
        mock_is_in_any_group.return_value = False

        @role_required("scientist")
        @group_required("/atlas")
        def protected_view():
            return {"status": "ok"}, 200

        with app.test_request_context():
            response = protected_view()
            # group_required is inner, so it's checked first
            assert response.status_code == 403
            assert b"membership" in response.data
