from datetime import datetime, timezone

from flask import Response, url_for
from pytest import fixture

from servicex_app.models import Dataset, DatasetStatus

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
