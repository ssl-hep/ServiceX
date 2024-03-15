from flask import Response, url_for

from pytest import fixture

from servicex.models import TransformRequest
from .web_test_base import WebTestBase


class TestTransformationRequest(WebTestBase):
    endpoint = "transformation_request"
    module = "servicex.web.transformation_request"
    template_name = 'transformation_request.html'

    @fixture
    def mock_tr_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformRequest")

    @fixture
    def mock_tr(self, mock_tr_cls) -> TransformRequest:
        req = self._test_transformation_req()
        mock_tr_cls.lookup.return_value = req
        return req

    def test_get_by_primary_key(self, client, mock_tr: TransformRequest, captured_templates):
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["req"] == mock_tr

    def test_get_by_uuid(self, client, mock_tr: TransformRequest, captured_templates):
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.request_id))
        assert resp.status_code == 200
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["req"] == mock_tr

    def test_404(self, client, mock_tr_cls):
        mock_tr_cls.lookup.return_value = None
        resp: Response = client.get(url_for(self.endpoint, id_=1))
        assert resp.status_code == 404
