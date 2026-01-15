import os
import pytest

import servicex_app


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
