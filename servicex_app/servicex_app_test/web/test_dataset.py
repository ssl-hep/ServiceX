from datetime import datetime, timedelta, timezone

from flask import Response, url_for
from pytest import fixture, mark

from servicex_app.models import Dataset, DatasetStatus, LogMessage, db

from .web_test_base import WebTestBase


class TestDatasetDetail(WebTestBase):

    @staticmethod
    def _fake_dataset(**overrides):
        defaults = {
            "id": 42,
            "name": "rucio://data25/foo.bar",
            "did_finder": "rucio",
            "last_used": datetime.now(tz=timezone.utc),
            "last_updated": datetime.now(tz=timezone.utc),
            "n_files": 3,
            "size": 1024,
            "events": 100,
            "lookup_status": DatasetStatus.complete,
            "stale": False,
        }
        defaults.update(overrides)
        ds = Dataset(**defaults)
        ds.files = []
        ds.transform_requests = []
        return ds

    @fixture
    def mock_find_by_id(self, mocker):
        return mocker.patch("servicex_app.web.dataset.Dataset.find_by_id")

    def test_renders_existing_dataset(
        self, client, user, mock_find_by_id, captured_templates
    ):
        ds = self._fake_dataset()
        mock_find_by_id.return_value = ds
        response: Response = client.get(
            url_for("dataset", id_=42), headers=self.fake_header()
        )
        assert response.status_code == 200
        mock_find_by_id.assert_called_once_with(42)
        template, context = captured_templates[0]
        assert template.name == "dataset.html"
        assert context["ds"] is ds

    def test_missing_dataset_returns_404(self, client, user, mock_find_by_id):
        mock_find_by_id.return_value = None
        response: Response = client.get(
            url_for("dataset", id_=999), headers=self.fake_header()
        )
        assert response.status_code == 404

    @staticmethod
    def _seed_logs(client, dataset_id, levels, request_id=None):
        """Insert one LogMessage per entry in `levels` for the given dataset.

        Pass `request_id` instead to seed transform-keyed records, which the
        dataset page must not show.
        """
        key = dataset_id if request_id is None else request_id
        with client.application.app_context():
            for i, level in enumerate(levels):
                db.session.add(
                    LogMessage(
                        id=f"{key}-{i}",
                        timestamp=datetime.utcnow() + timedelta(seconds=i),
                        level=level,
                        level_no=LogMessage.LEVELS.get(level, 0),
                        component="did-finder-rucio",
                        message=f"message {i}",
                        dataset_id=None if request_id else dataset_id,
                        request_id=request_id,
                    )
                )
            db.session.commit()

    def _get(self, client, **args):
        response: Response = client.get(
            url_for("dataset", id_=42, **args), headers=self.fake_header()
        )
        assert response.status_code == 200
        return response

    def test_logs_for_dataset(self, client, user, mock_find_by_id, captured_templates):
        mock_find_by_id.return_value = self._fake_dataset()
        self._seed_logs(client, 42, ["INFO", "ERROR", "INFO"])
        response = self._get(client)
        _, context = captured_templates[0]
        assert [msg.message for msg in context["logs"]] == [
            "message 2",
            "message 1",
            "message 0",
        ]
        html = response.data.decode()
        assert 'class="log-grid' in html
        assert 'id="logMessageModal"' in html
        assert 'data-target="#logMessageModal"' in html

    def test_logs_only_for_this_dataset(
        self, client, user, mock_find_by_id, captured_templates
    ):
        mock_find_by_id.return_value = self._fake_dataset()
        self._seed_logs(client, 42, ["INFO"])
        self._seed_logs(client, 43, ["ERROR", "ERROR"])
        self._seed_logs(client, None, ["ERROR"], request_id="some-request-id")
        self._get(client)
        _, context = captured_templates[0]
        assert len(context["logs"]) == 1

    def test_no_logs(self, client, user, mock_find_by_id, captured_templates):
        mock_find_by_id.return_value = self._fake_dataset()
        response = self._get(client)
        _, context = captured_templates[0]
        assert context["logs"] == []
        assert "No log messages." in response.data.decode()

    ALL_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @mark.parametrize(
        "query, active, levels",
        [
            ("WARNING", "WARNING", {"WARNING", "ERROR", "CRITICAL"}),
            ("error", "ERROR", {"ERROR", "CRITICAL"}),  # case insensitive
            ("BOGUS", None, set(ALL_LEVELS)),  # an unknown level is no filter
        ],
    )
    def test_logs_filtered_by_level(
        self,
        client,
        user,
        mock_find_by_id,
        captured_templates,
        query,
        active,
        levels,
    ):
        mock_find_by_id.return_value = self._fake_dataset()
        self._seed_logs(client, 42, self.ALL_LEVELS)
        self._get(client, log_level=query)
        _, context = captured_templates[0]
        assert context["active_level"] == active
        assert {msg.level for msg in context["logs"]} == levels

    def test_logs_capped_to_newest(
        self, client, user, mock_find_by_id, captured_templates, mocker
    ):
        mocker.patch("servicex_app.web.dataset.MAX_DATASET_LOGS", 3)
        mock_find_by_id.return_value = self._fake_dataset()
        self._seed_logs(client, 42, ["INFO"] * 5)
        response = self._get(client)
        _, context = captured_templates[0]
        assert [msg.message for msg in context["logs"]] == [
            "message 4",
            "message 3",
            "message 2",
        ]
        assert "Showing the newest 3 messages." in response.data.decode()
