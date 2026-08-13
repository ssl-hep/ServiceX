from flask import Response, url_for
from pytest import fixture

from .web_test_base import WebTestBase


class TestDatasets(WebTestBase):

    @fixture
    def mock_query(self, mocker):
        mock_ds = mocker.patch("servicex_app.web.datasets.Dataset")
        query = mock_ds.query
        filtered = query.filter_by.return_value
        return {
            "raw": query.order_by.return_value,
            "filtered": filtered.order_by.return_value,
        }

    def test_default_filters_out_stale(self, client, user, mock_query, captured_templates):
        pagination = mock_query["filtered"].paginate(
            page=1, per_page=15, total=0, items=[]
        )
        mock_query["filtered"].paginate.return_value = pagination
        response: Response = client.get(
            url_for("datasets"), headers=self.fake_header()
        )
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "datasets.html"
        assert context["pagination"] == pagination
        assert context["active_sort"] == "last_used"
        assert context["active_order"] == "desc"
        assert context["show_deleted"] is False

    def test_show_deleted_true_skips_stale_filter(
        self, client, user, mock_query, captured_templates
    ):
        pagination = mock_query["raw"].paginate(
            page=1, per_page=15, total=0, items=[]
        )
        mock_query["raw"].paginate.return_value = pagination
        response: Response = client.get(
            url_for("datasets") + "?show_deleted=true",
            headers=self.fake_header(),
        )
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "datasets.html"
        assert context["show_deleted"] is True

    def test_sort_and_order_are_applied(
        self, client, user, mock_query, captured_templates
    ):
        pagination = mock_query["filtered"].paginate(
            page=1, per_page=15, total=0, items=[]
        )
        mock_query["filtered"].paginate.return_value = pagination
        response: Response = client.get(
            url_for("datasets") + "?sort=events&order=asc",
            headers=self.fake_header(),
        )
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert context["active_sort"] == "events"
        assert context["active_order"] == "asc"

    def test_invalid_sort_choice_returns_400(self, client, user, mock_query):
        response: Response = client.get(
            url_for("datasets") + "?sort=bogus",
            headers=self.fake_header(),
        )
        assert response.status_code == 400
