import pytest
from flask import session
from flask_jwt_extended.exceptions import NoAuthorizationError

from servicex_app.web.admin import AdminAuthMixin
from servicex_app_test.web.web_test_base import WebTestBase


class TestAdminAuthMixin(WebTestBase):
    @pytest.fixture
    def mixin(self):
        return AdminAuthMixin()

    @pytest.fixture
    def auth_client(self):
        return self._test_client(extra_config={"ENABLE_AUTH": True})

    def test_is_admin_false_when_auth_disabled(self, client, mixin):
        with client.application.test_request_context():
            assert mixin._is_admin() is False

    def test_is_admin_true_with_session_admin(self, auth_client, mixin):
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            session["admin"] = True
            assert mixin._is_admin() is True

    def test_is_admin_false_with_session_not_admin(self, auth_client, mixin):
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            session["admin"] = False
            assert mixin._is_admin() is False

    def test_is_admin_false_with_session_authenticated_but_no_admin_key(
        self, auth_client, mixin, mocker
    ):
        mocker.patch(
            "servicex_app.web.admin.verify_jwt_in_request",
            side_effect=NoAuthorizationError("no token"),
        )
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            assert mixin._is_admin() is False

    def test_is_admin_true_with_jwt_admin_user(self, auth_client, mixin, mocker):
        mock_user = mocker.MagicMock()
        mock_user.admin = True
        mocker.patch("servicex_app.web.admin.verify_jwt_in_request")
        mocker.patch("servicex_app.web.admin.get_jwt_user", return_value=mock_user)
        with auth_client.application.test_request_context():
            assert mixin._is_admin() is True

    def test_is_admin_false_with_jwt_non_admin_user(self, auth_client, mixin, mocker):
        mock_user = mocker.MagicMock()
        mock_user.admin = False
        mocker.patch("servicex_app.web.admin.verify_jwt_in_request")
        mocker.patch("servicex_app.web.admin.get_jwt_user", return_value=mock_user)
        with auth_client.application.test_request_context():
            assert mixin._is_admin() is False

    def test_is_admin_false_on_no_authorization_error(
        self, auth_client, mixin, mocker
    ):
        mocker.patch(
            "servicex_app.web.admin.verify_jwt_in_request",
            side_effect=NoAuthorizationError("no token"),
        )
        with auth_client.application.test_request_context():
            assert mixin._is_admin() is False

    def test_is_admin_false_on_generic_exception(self, auth_client, mixin, mocker):
        mocker.patch(
            "servicex_app.web.admin.verify_jwt_in_request",
            side_effect=RuntimeError("unexpected"),
        )
        with auth_client.application.test_request_context():
            assert mixin._is_admin() is False
