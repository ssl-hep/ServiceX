from flask import Response, url_for

from pytest import fixture

from servicex_app.models import TransformRequest
from .web_test_base import WebTestBase


class TestTransformationRequest(WebTestBase):
    endpoint = "transformation_request"
    module = "servicex_app.web.transformation_request"
    template_name = "transformation_request.html"

    @fixture
    def mock_lookup(self, mocker):
        return mocker.patch("servicex_app.models.TransformRequest.lookup")

    @fixture
    def mock_tr(self, mock_lookup) -> TransformRequest:
        req = self._test_transformation_req()
        mock_lookup.return_value = req
        return req

    def test_get_by_primary_key(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
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

    def test_404(self, client, mock_lookup):
        mock_lookup.return_value = None
        resp: Response = client.get(url_for(self.endpoint, id_=1))
        assert resp.status_code == 404

    @fixture
    def auth_client(self):
        return self._test_client(extra_config={"ENABLE_AUTH": True})

    @fixture
    def signed_in(self, auth_client, user):
        user.id = 42
        user.admin = False
        with auth_client.session_transaction() as sess:
            sess["is_authenticated"] = True
            sess["user_id"] = user.id
        return user

    def test_403_for_non_owner(self, auth_client, signed_in, mock_tr: TransformRequest):
        mock_tr.submitted_by = 43
        resp: Response = auth_client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 403

    def test_owner_allowed(self, auth_client, signed_in, mock_tr: TransformRequest):
        mock_tr.submitted_by = 42
        resp: Response = auth_client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200

    def test_admin_allowed(self, auth_client, signed_in, mock_tr: TransformRequest):
        signed_in.admin = True
        mock_tr.submitted_by = 43
        resp: Response = auth_client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200

    def test_stale_session_admin_flag_ignored(
        self, auth_client, signed_in, mock_tr: TransformRequest
    ):
        # Admin rights come from the database, not the flag cached at sign-in
        mock_tr.submitted_by = 43
        with auth_client.session_transaction() as sess:
            sess["admin"] = True
        resp: Response = auth_client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 403
