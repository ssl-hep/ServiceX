from unittest.mock import MagicMock

from pytest import fixture

from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformerJobStatus(ResourceTestBase):
    module = "servicex_app.resources.transformation.job_status"

    @fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_transformer_job_status.return_value = None
        return mock_transform_manager

    @fixture
    def mock_job_status(self) -> MagicMock:
        mock_job_status = MagicMock()
        mock_job_status.to_dict.return_value = {
            "active": 17,
            "completion_time": None,
            "conditions": None,
            "failed": None,
            "ready": 17,
            "start_time": "2026-10-05T12:00:00+00:00",
            "succeeded": None,
            "uncounted_terminated_pods": None,
        }
        return mock_job_status

    def test_job_status(self, mock_transform_manager, mock_job_status):
        mock_transform_manager.get_transformer_job_status.return_value = mock_job_status

        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/job-status")
        assert response.status_code == 200
        assert response.json == mock_job_status.to_dict.return_value

    def test_job_status_reports_active_pods(
        self, mock_transform_manager, mock_job_status
    ):
        mock_transform_manager.get_transformer_job_status.return_value = mock_job_status

        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/job-status")
        assert response.json["active"] == 17

    def test_job_status_404(self, mock_transform_manager):
        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/job-status")
        assert response.status_code == 404
