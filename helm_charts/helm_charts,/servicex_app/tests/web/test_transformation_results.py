from typing import List

from flask import Response, url_for
from flask_sqlalchemy import Pagination

import pytest

from servicex.models import TransformRequest, TransformationResult
from .web_test_base import WebTestBase

statuses = ["success", "failure"]


class TestUserDashboard(WebTestBase):
    endpoint = "transformation_results"
    module = "servicex.web.transformation_results"
    template_name = 'transformation_results.html'

    @pytest.fixture
    def mock_tr_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformRequest")

    @pytest.fixture
    def mock_tr(self, mock_tr_cls) -> TransformRequest:
        req = self._test_transformation_req()
        mock_tr_cls.lookup.return_value = req
        return req

    @pytest.fixture
    def mock_result_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformationResult")

    def _fake_transformation_results(self) -> List[TransformationResult]:
        results = [TransformationResult(transform_status=status) for status in statuses]
        return results

    def test_get_empty_state(self, client, mock_tr, mock_result_cls, captured_templates):
        mock_result_query = mock_result_cls.query.filter_by.return_value.order_by.return_value
        pagination = Pagination(mock_result_query, page=1, per_page=100, total=0, items=[])
        mock_result_query.paginate.return_value = pagination
        response: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert response.status_code == 200
        mock_result_cls.query.filter_by.assert_called_once_with(request_id=mock_tr.request_id)
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["pagination"] == pagination

    @pytest.mark.parametrize("status", [None, *statuses])
    def test_get_with_results(
        self, client, mock_tr, mock_result_cls, status, captured_templates
    ):
        mock_result_query = mock_result_cls.query.filter_by.return_value.order_by.return_value
        items = [r for r in self._fake_transformation_results() if r.transform_status == status]
        pagination = Pagination(mock_result_query, page=1, per_page=100, total=0, items=items)
        mock_result_query.paginate.return_value = pagination
        query_params = {"status": status} if status is not None else {}
        url = url_for(self.endpoint, id_=mock_tr.id, **query_params)
        response: Response = client.get(url)
        assert response.status_code == 200
        query_kwargs = {"transform_status": status} if status is not None else {}
        mock_result_cls.query.filter_by.assert_called_once_with(
            request_id=mock_tr.request_id, **query_kwargs
        )
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["pagination"] == pagination

    def test_404(self, client, mock_tr_cls):
        mock_tr_cls.lookup.return_value = None
        resp: Response = client.get(url_for(self.endpoint, id_=1))
        assert resp.status_code == 404
