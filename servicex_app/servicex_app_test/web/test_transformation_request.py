import json
import re
from datetime import datetime, timedelta
from html import unescape

from flask import Response, url_for
from markupsafe import escape

from pytest import fixture, mark

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
    def _seed_logs(client, request_id, levels, messages=None, extras=None):
        """Insert one LogMessage per entry in `levels` for the given request.

        `messages` and `extras` override the body and the `extra` payload of
        each record, one entry per level, for tests that care about how the
        log record itself is rendered.
        """
        with client.application.app_context():
            for i, level in enumerate(levels):
                db.session.add(
                    LogMessage(
                        id=f"{request_id}-{i}",
                        timestamp=datetime.utcnow() + timedelta(seconds=i),
                        level=level,
                        # The vector aggregator derives this from the level
                        # name for every record; mirror it here so the seeded
                        # rows exercise the real filter.
                        level_no=LogMessage.LEVELS.get(level, 0),
                        component="transformer",
                        message=messages[i] if messages else f"message {i}",
                        extra=extras[i] if extras else None,
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

    ALL_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @mark.parametrize(
        "query, active, total",
        [
            ("WARNING", "WARNING", 3),  # a minimum: WARNING and everything above
            ("DEBUG", "DEBUG", 5),  # the lowest level matches everything
            ("CRITICAL", "CRITICAL", 1),  # the highest matches only itself
            ("error", "ERROR", 2),  # the filter is case insensitive
            ("BOGUS", None, 5),  # an unknown level is no filter at all
        ],
    )
    def test_logs_filtered_by_level(
        self,
        client,
        mock_tr: TransformRequest,
        captured_templates,
        query,
        active,
        total,
    ):
        self._seed_logs(client, mock_tr.request_id, self.ALL_LEVELS)
        resp: Response = client.get(
            url_for(self.endpoint, id_=mock_tr.id, log_level=query)
        )
        assert resp.status_code == 200
        _, context = captured_templates[0]
        assert context["active_level"] == active
        assert context["logs"].total == total

    def test_logs_filter_selects_the_levels_at_or_above(
        self, client, mock_tr: TransformRequest, captured_templates
    ):
        self._seed_logs(client, mock_tr.request_id, self.ALL_LEVELS)
        resp: Response = client.get(
            url_for(self.endpoint, id_=mock_tr.id, log_level="WARNING")
        )
        assert resp.status_code == 200
        _, context = captured_templates[0]
        assert {msg.level for msg in context["logs"].items} == {
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

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

    def test_long_log_message_is_truncated_in_grid(
        self, client, mock_tr: TransformRequest
    ):
        long_message = 'Traceback (most recent call last):\n  File "<stdin>"\n' + (
            "spam " * 100
        )
        self._seed_logs(client, mock_tr.request_id, ["ERROR"], [long_message])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        html = resp.data.decode()
        # The grid shows an elided fragment...
        preview = re.search(
            r'<span class="log-message-preview">(.*?)</span>', html, re.DOTALL
        ).group(1)
        assert preview.endswith("\u2026")
        assert len(preview) < len(long_message)
        # ...while the View link carries the whole thing for the dialog.
        assert f'data-message="{escape(long_message)}"' in html

    def test_short_log_message_is_not_truncated(
        self, client, mock_tr: TransformRequest
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO"], ["a short message"])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "a short message" in html
        assert "\u2026" not in html

    def test_log_message_dialog_is_rendered(self, client, mock_tr: TransformRequest):
        self._seed_logs(client, mock_tr.request_id, ["INFO"])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="logMessageModal"' in html
        assert 'data-target="#logMessageModal"' in html
        assert ">View</a>" in html

    def test_log_message_extra_is_available_to_dialog(
        self, client, mock_tr: TransformRequest
    ):
        extra = {"file_id": 7, "note": 'quoted "value" & <tag>'}
        self._seed_logs(client, mock_tr.request_id, ["INFO"], extras=[extra])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="logMessageExtra"' in html
        # The payload rides along as escaped JSON on the View link: what the
        # browser hands the dialog must parse back to the original object.
        attr = re.search(r'data-extra="(.*?)"', html, re.DOTALL).group(1)
        assert json.loads(unescape(attr)) == extra

    def test_log_message_without_extra_omits_attribute(
        self, client, mock_tr: TransformRequest
    ):
        self._seed_logs(client, mock_tr.request_id, ["INFO"])
        resp: Response = client.get(url_for(self.endpoint, id_=mock_tr.id))
        assert resp.status_code == 200
        assert "data-extra=" not in resp.data.decode()
