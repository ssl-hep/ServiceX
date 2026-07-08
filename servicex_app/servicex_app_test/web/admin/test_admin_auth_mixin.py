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
            assert mixin.is_accessible() is False

    def test_is_admin_true_with_session_admin(self, auth_client, mixin, user):
        user.admin = True
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            session["email"] = user.email
            assert mixin.is_accessible() is True

    def test_is_admin_false_with_session_not_admin(self, auth_client, mixin, user):
        user.admin = False
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            session["email"] = user.email
            assert mixin.is_accessible() is False

    def test_is_admin_false_with_session_authenticated_but_no_admin_key(
        self, auth_client, mixin
    ):
        with auth_client.application.test_request_context():
            session["is_authenticated"] = True
            assert mixin.is_accessible() is False

    def test_is_admin_false_on_no_authorization_error(self, auth_client, mixin, mocker):
        mocker.patch(
            "servicex_app.decorators.verify_jwt_in_request",
            side_effect=NoAuthorizationError("no token"),
        )
        with auth_client.application.test_request_context():
            assert mixin.is_accessible() is False

    def test_is_admin_false_on_generic_exception(self, auth_client, mixin, mocker):
        mocker.patch(
            "servicex_app.decorators.verify_jwt_in_request",
            side_effect=RuntimeError("unexpected"),
        )
        with auth_client.application.test_request_context():
            assert mixin.is_accessible() is False

    def test_inaccessible_callback_redirects_to_home(self, auth_client):
        response = auth_client.get("/admin/")
        assert response.status_code == 302
        assert response.location == "/"
