from unittest.mock import MagicMock

import kubernetes as k8s
import pytest

from servicex_app.models import TransformRequest, TransformStatus
from tests.resource_test_base import ResourceTestBase


class TestTransformCancel(ResourceTestBase):
    module = "servicex_app.resources.transformation.cancel"

    @pytest.fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_deployment_status.return_value = None
        return mock_transform_manager

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        mock_transform_request_cls = mocker.patch(f"{self.module}.TransformRequest")
        fake_transform = self._generate_transform_request()
        fake_transform.save_to_db = mocker.Mock()
        mock_transform_request_cls.lookup.return_value = fake_transform
        return fake_transform

    def test_submitted(self, fake_transform, mock_transform_manager):
        fake_transform.status = TransformStatus.submitted
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 200
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None
        mock_transform_manager.shutdown_transformer_job.assert_not_called()

    def test_running(self, mock_transform_manager, fake_transform):
        fake_transform.status = TransformStatus.running
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 200
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_transform_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_deployment_not_found(self, mock_transform_manager, fake_transform):
        fake_transform.status = TransformStatus.running
        exc = k8s.client.exceptions.ApiException(status=404)
        mock_transform_manager.shutdown_transformer_job.side_effect = exc
        client = self._test_client(transformation_manager=mock_transform_manager)
        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 200
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_transform_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_k8s_exception(self, mock_transform_manager, fake_transform):
        fake_transform.status = TransformStatus.running
        exc = k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        mock_transform_manager.shutdown_transformer_job.side_effect = exc
        client = self._test_client(transformation_manager=mock_transform_manager)
        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 403
        namespace = client.application.config["TRANSFORMER_NAMESPACE"]
        mock_transform_manager.shutdown_transformer_job.assert_called_once_with("1234", namespace)
        assert fake_transform.status == TransformStatus.running
        assert fake_transform.finish_time is None

    @pytest.mark.parametrize("status", [
        TransformStatus.complete,
        TransformStatus.fatal,
        TransformStatus.canceled
    ])
    def test_complete(self, client, fake_transform, status: TransformStatus):
        fake_transform.status = status
        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 400
        assert "not in progress" in resp.json["message"]

    def test_404(self, client):
        resp = client.get("/servicex/transformation/1234/cancel")
        assert resp.status_code == 404
        assert "Transformation request not found" in resp.json["message"]
