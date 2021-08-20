from unittest.mock import MagicMock

import kubernetes as k8s
import pytest

from servicex.models import TransformRequest
from tests.resource_test_base import ResourceTestBase


class TestTransformStart(ResourceTestBase):
    module = "servicex.resources.transform_stop"

    @pytest.fixture
    def mock_manager(self, mocker) -> MagicMock:
        mock_transform_start_resource = mocker.patch(f"{self.module}.TransformStart")
        return mock_transform_start_resource.transformer_manager

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        mock_transform_request_cls = mocker.patch(f"{self.module}.TransformRequest")
        fake_transform = self._generate_transform_request()
        fake_transform.save_to_db = mocker.Mock()
        mock_transform_request_cls.return_request.return_value = fake_transform
        return fake_transform

    def test_submitted(self, client, mock_manager, fake_transform):
        fake_transform.status = "Submitted"
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 200
        assert fake_transform.status == "Stopped"
        mock_manager.shutdown_transformer_job.assert_not_called()

    def test_running(self, client, mock_manager, fake_transform):
        fake_transform.status = "Running"
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 200
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == "Stopped"

    def test_running_deployment_not_found(self, client, mock_manager, fake_transform):
        fake_transform.status = "Running"
        exc = k8s.client.exceptions.ApiException(status=404)
        mock_manager.shutdown_transformer_job.side_effect = exc
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 200
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == "Stopped"

    def test_running_k8s_exception(self, client, mock_manager, fake_transform):
        fake_transform.status = "Running"
        exc = k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        mock_manager.shutdown_transformer_job.side_effect = exc
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 403
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == "Running"

    @pytest.mark.parametrize("status", [
        "Complete",
        "Fatal",
        "Stopped"
    ])
    def test_complete(self, client, fake_transform, status: str):
        fake_transform.status = status
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 400
        assert "already complete" in resp.json["message"]

    def test_404(self, client):
        resp = client.get("/servicex/transformation/1234/stop")
        assert resp.status_code == 404
        assert "Transformation request not found" in resp.json["message"]
