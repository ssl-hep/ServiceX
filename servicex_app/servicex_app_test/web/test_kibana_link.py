import pytest
from flask import Flask

from servicex_app.web import (
    LogLevel,
    add_query,
    create_kibana_link_parameters,
)

SAMPLE_LOGS_URL = "http://kibana.example.com/app/discover#/?_t=foo&_g=()"


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["LOGS_URL"] = SAMPLE_LOGS_URL
    return app


class TestAddQuery:
    def test_formats_request_id(self):
        result = add_query("requestId", "abc-123")
        assert result == "(query:(match_phrase:(requestId:'abc-123')))"

    def test_formats_level(self):
        result = add_query("level", "info")
        assert result == "(query:(match_phrase:(level:'info')))"


class TestCreateKibanaLinkParameters:
    def test_default_log_level_is_info(self, app):
        with app.app_context():
            result = create_kibana_link_parameters(transform_id="abc-123")
        assert "(query:(match_phrase:(level:'info')))" in result
        assert "(query:(match_phrase:(requestId:'abc-123')))" in result

    def test_error_log_level(self, app):
        with app.app_context():
            result = create_kibana_link_parameters(
                transform_id="abc-123",
                log_level=LogLevel.error,
            )
        assert "(query:(match_phrase:(level:'error')))" in result
        assert "(query:(match_phrase:(requestId:'abc-123')))" in result

    def test_no_log_level_omits_level_filter(self, app):
        with app.app_context():
            with pytest.raises(
                AssertionError, match="Log level must be one of INFO or ERROR"
            ):
                _ = create_kibana_link_parameters(
                    transform_id="abc-123",
                    log_level=None,
                )

    def test_replaces_g_parameter_in_url(self, app):
        with app.app_context():
            result = create_kibana_link_parameters(transform_id="abc-123")
        assert "&_g=()" not in result
        assert result.startswith("http://kibana.example.com/app/discover#/?_t=foo")

    def test_full_url_with_info_level(self, app):
        with app.app_context():
            result = create_kibana_link_parameters(transform_id="abc-123")
        expected = (
            "http://kibana.example.com/app/discover#/?_t=foo"
            "&_a=(filters:!("
            "(query:(match_phrase:(requestId:'abc-123'))),"
            "(query:(match_phrase:(level:'info')))"
            "))"
        )
        assert result == expected

    def test_no_substitution_when_pattern_missing(self, app):
        app.config["LOGS_URL"] = "http://kibana.example.com/app/discover#/"
        with app.app_context():
            result = create_kibana_link_parameters(transform_id="abc-123")
        assert result == "http://kibana.example.com/app/discover#/"
