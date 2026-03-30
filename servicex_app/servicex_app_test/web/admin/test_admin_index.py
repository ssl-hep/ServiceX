import pytest
from flask import template_rendered

from servicex_app_test.web.web_test_base import WebTestBase


class TestSecureAdminIndexView(WebTestBase):
    @pytest.fixture
    def admin_client(self):
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.session_transaction() as sess:
            sess["is_authenticated"] = True
            sess["admin"] = True
        return client

    @pytest.fixture
    def captured(self, admin_client):
        recorded = []

        def record(sender, template, context, **extra):
            recorded.append((template, context))

        template_rendered.connect(record, admin_client.application)
        try:
            yield recorded
        finally:
            template_rendered.disconnect(record, admin_client.application)

    def test_index_returns_200_for_admin(self, admin_client):
        response = admin_client.get("/admin/")
        assert response.status_code == 200

    def test_index_includes_model_views(self, admin_client, captured):
        admin_client.get("/admin/")
        contexts = [ctx for _, ctx in captured if "model_views" in ctx]
        assert contexts
        model_view_names = [v["name"] for v in contexts[0]["model_views"]]
        assert "User" in model_view_names

    def test_index_includes_report_views(self, admin_client, captured):
        admin_client.get("/admin/")
        contexts = [ctx for _, ctx in captured if "report_views" in ctx]
        assert contexts
        report_view_names = [v["name"] for v in contexts[0]["report_views"]]
        assert "User Transformation Count" in report_view_names
