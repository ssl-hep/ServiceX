from flask import Response, url_for
from flask_sqlalchemy import Pagination

from pytest import fixture

from .web_test_base import WebTestBase


class TestGlobalDashboard(WebTestBase):

    @fixture
    def mock_query(self, mocker):
        mock_tr = mocker.patch("servicex.web.dashboard.TransformRequest")
        return mock_tr.query.order_by.return_value

    def test_get_empty_state(self, client, user, mock_query, captured_templates):
        pagination = Pagination(mock_query, page=1, per_page=15, total=0, items=[])
        mock_query.paginate.return_value = pagination
        response: Response = client.get(url_for('global-dashboard'))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "global_dashboard.html"
        assert context["pagination"] == pagination

    def test_get_with_results(self, client, user, mock_query, captured_templates):
        items = [self._test_transformation_req(id=i+1) for i in range(3)]
        pagination = Pagination(mock_query, page=1, per_page=15, total=100, items=items)
        mock_query.paginate.return_value = pagination
        response: Response = client.get(url_for('global-dashboard'))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "global_dashboard.html"
        assert context["pagination"] == pagination
