from servicex_app.web.kibana_url_filter import filter_kibana_url


class TestAddRequestIdFilter:
    """Tests for add_request_id_filter using a real Kibana dashboard URL."""

    EXAMPLE_URL = (
        "https://atlas-kibana.mwt2.org:5601/s/servicex/app/dashboards"
        "?auth_provider_hint=anonymous1#/view/bb682100-5558-11ed-afcf-d91dad577662#"
        "?embed=true"
        "&_g=(filters:!(),refreshInterval:(pause:!t,value:1000),"
        "time:(from:now-24h/h,to:now))"
        "&_a=(filters:!((query:(match_phrase:(instance:servicex-unit-test))))"
        ",index:'923eaa00-45b9-11ed-afcf-d91dad577662')"
    )

    def test_preserves_base_url(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert result.startswith(
            "https://atlas-kibana.mwt2.org:5601/s/servicex/app/dashboards"
        )

    def test_preserves_auth_query(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "?auth_provider_hint=anonymous1" in result

    def test_preserves_view_path(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "#/view/bb682100-5558-11ed-afcf-d91dad577662" in result

    def test_includes_embed_true(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "embed=true" in result

    def test_preserves_instance_in_query(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "servicex-unit-test" in result

    def test_includes_request_id_in_query(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "abc-123" in result

    def test_includes_log_level_in_query(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="DEBUG")
        assert "level%3ADEBUG" in result

    def test_includes_app_state_filter(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "_a=" in result
        assert "requestId" in result

    def test_preserves_time_range(self):
        result = filter_kibana_url(self.EXAMPLE_URL, "abc-123", log_level="INFO")
        assert "now-24h/h" in result
        assert "to:now" in result
