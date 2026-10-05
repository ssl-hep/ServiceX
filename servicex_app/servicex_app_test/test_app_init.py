import os
import pytest

import servicex_app
from servicex_app import strtobool


class TestStrToBool:
    @pytest.mark.parametrize(
        "value", ["y", "yes", "t", "true", "on", "1", "Y", "YES", "True", "ON"]
    )
    def test_truthy_values(self, value):
        assert strtobool(value) is True

    @pytest.mark.parametrize(
        "value", ["n", "no", "f", "false", "off", "0", "N", "NO", "False", "OFF"]
    )
    def test_falsy_values(self, value):
        assert strtobool(value) is False

    @pytest.mark.parametrize("value", ["", "maybe", "2", "yesplease"])
    def test_invalid_value_raises(self, value):
        with pytest.raises(ValueError, match="invalid truth value"):
            strtobool(value)


class TestAppInit:
    def test_read_from_config(self):
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        os.environ["ALLOWED_IMAGE_PREFIXES"] = '["sslhep/"]'
        app = servicex_app.create_app()
        assert app.config["FOO"] == "bar"
        assert app.config["SECRET_VALUE"] == "blah"
        assert not app.config["BOOL_VALUE"]

        os.environ["SECRET_VALUE"] = "shhh"
        os.environ["BOOL_VALUE"] = "true"
        app_from_env = servicex_app.create_app()
        assert app_from_env.config["SECRET_VALUE"] == "shhh"
        assert app_from_env.config["BOOL_VALUE"]

    def test_app_init_without_allowed_prefixes(self, monkeypatch):
        """Test that app creation fails when ALLOWED_IMAGE_PREFIXES is not set"""
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        monkeypatch.delenv("ALLOWED_IMAGE_PREFIXES", raising=False)
        with pytest.raises(ValueError, match="must be configured"):
            servicex_app.create_app()


class TestUserCli:
    @pytest.fixture
    def app(self):
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        os.environ["ALLOWED_IMAGE_PREFIXES"] = '["sslhep/"]'
        return servicex_app.create_app()

    def test_approve_command_dispatches_to_approve_user(self, app, mocker):
        mock = mocker.patch("servicex_app.approve_user")
        result = app.test_cli_runner().invoke(args=["user", "approve", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com")

    def test_make_admin_command_dispatches_to_set_user_admin(self, app, mocker):
        mock = mocker.patch("servicex_app.set_user_admin")
        result = app.test_cli_runner().invoke(args=["user", "make-admin", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com", True)

    def test_revoke_admin_command_dispatches_to_set_user_admin(self, app, mocker):
        mock = mocker.patch("servicex_app.set_user_admin")
        result = app.test_cli_runner().invoke(args=["user", "revoke-admin", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com", False)
