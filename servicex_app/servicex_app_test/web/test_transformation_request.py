from datetime import datetime, timedelta

from flask import Response, url_for

from pytest import fixture

from servicex_app.models import TransformRequest, LogMessage, db
from .web_test_base import WebTestBase


class TestTransformationRequest(WebTestBase):
    endpoint = "transformation_request"
    module = "servicex_app.web.transformation_request"
    template_name = "transformation_request.html"

    @fixture
    def mock_tr_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformRequest")

    @fixture
    def mock_tr(self, mock_tr_cls) -> TransformRequest:
        req = self._test_transformation_req()
        mock_tr_cls.lookup.return_value = req
        return req

    @staticmethod
    def _seed_logs(client, request_id, levels):
        """Insert one LogMessage per entry in `levels` for the given request."""
        with client.application.app_context():
            for i, level in enumerate(levels):
                db.session.add(
                    LogMessage(
                        id=f"{request_id}-{i}",
                        timestamp=datetime.utcnow() + timedelta(seconds=i),
                        level=level,
                        component="transformer",
                        message=f"message {i}",
                        request_id=request_id,
                    )
                )
            db.session.commit()

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

    def test_404(self, client, mock_tr_cls):
        mock_tr_cls.lookup.return_value = None
        resp: Response = client.get(url_for(self.endpoint, id_=1))
        assert resp.status_code == 404

    def test_logs_for_request(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO", "ERROR", "INFO"])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        _, context = captured_templates[0]
        assert context["logs"].total == 3
        # Newest first: last-seeded message is on top.
        assert context["logs"].items[0].message == "message 2"

    def test_logs_only_for_this_request(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO"])
        self._seed_logs(client, "some-other-request-id", ["ERROR", "ERROR"])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        _, context = captured_templates[0]
        assert context["logs"].total == 1

    def test_logs_filtered_by_level(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO", "ERROR", "INFO"])
        resp: Response = client.get(
            url_for(self.endpoint, id_=mock_tr.id, log_level="ERROR")
        )
        assert resp.status_code == 200
        _, context = captured_templates[0]
        assert context["active_level"] == "ERROR"
        assert context["logs"].total == 1
        assert context["logs"].items[0].level == "ERROR"

    def test_logs_paginated(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO"] * 60)
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id, page=2))
        assert resp.status_code == 200
        _, context = captured_templates[0]
        # per_page is 50, so page 2 holds the remaining 10.
        assert context["logs"].total == 60
        assert len(context["logs"].items) == 10
