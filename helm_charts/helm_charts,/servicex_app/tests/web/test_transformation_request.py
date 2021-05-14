from flask import Response, url_for

from pytest import fixture

from .web_test_base import WebTestBase


class TestTransformationRequest(WebTestBase):
    template_name = 'transformation_request.html'

    @fixture
    def mock_tr(self, mocker):
        return mocker.patch("servicex.web.transformation_request.TransformRequest")

    def test_get_by_primary_key(self, client, mock_tr, captured_templates):
        req = self._test_transformation_req()
        mock_tr.query.get.return_value = req
        resp: Response = client.get(url_for('transformation_request', id_=req.id))
        assert resp.status_code == 200
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["req"] == req
        mock_tr.query.get.assert_called_once_with(str(req.id))
        mock_tr.query.filter_by.assert_not_called()

    def test_get_by_uuid(self, client, mocker, mock_tr, captured_templates):
        req = self._test_transformation_req()
        mock_query = mocker.MagicMock()
        mock_tr.query.filter_by.return_value = mock_query
        mock_query.one.return_value = req
        resp: Response = client.get(url_for('transformation_request', id_=req.request_id))
        assert resp.status_code == 200
        template, context = captured_templates[0]
        assert template.name == self.template_name
        assert context["req"] == req
        mock_tr.query.filter_by.assert_called_once_with(request_id=req.request_id)
        mock_tr.query.get.assert_not_called()
        mock_query.one.assert_called_once()

    def test_404(self, client, mock_tr):
        mock_tr.query.get.return_value = None
        resp: Response = client.get(url_for('transformation_request', id_=1))
        assert resp.status_code == 404
