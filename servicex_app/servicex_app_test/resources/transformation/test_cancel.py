from unittest.mock import MagicMock

import kubernetes as k8s
import pytest

from servicex_app.models import TransformRequest, TransformStatus
from servicex_app_test.resource_test_base import ResourceTestBase

URL = "/servicex/transformation/1234/cancel"


class TestTransformCancel(ResourceTestBase):
    module = "servicex_app.resources.transformation.cancel"

    @pytest.fixture(params=["get", "post"])
    def http_method(self, request):
        return request.param

    @pytest.fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_deployment_status.return_value = None
        return mock_transform_manager

    @pytest.fixture
    def mock_transform_request_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformRequest")

    @pytest.fixture
    def fake_transform(self, mock_transform_request_cls, mocker) -> TransformRequest:
        fake = self._generate_transform_request()
        fake.save_to_db = mocker.Mock()
        mock_transform_request_cls.lookup.return_value = fake
        return fake

    def test_submitted(
        self,
        http_method,
        fake_transform,
        mock_transform_request_cls,
        mock_transform_manager,
    ):
        fake_transform.status = TransformStatus.submitted
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None
        mock_transform_request_cls.shutdown_pod.assert_called_once_with(fake_transform)

    def test_running(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
        mock_transform_request_cls,
    ):
        fake_transform.status = TransformStatus.running
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        mock_transform_request_cls.shutdown_pod.assert_called_once_with(fake_transform)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_deployment_not_found(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
        mock_transform_request_cls,
    ):
        fake_transform.status = TransformStatus.running
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        mock_transform_request_cls.shutdown_pod.assert_called_once_with(fake_transform)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_k8s_exception(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
        mock_transform_request_cls,
    ):
        fake_transform.status = TransformStatus.running
        exc = k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        mock_transform_request_cls.shutdown_pod.side_effect = exc
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 403
        mock_transform_request_cls.shutdown_pod.assert_called_once_with(fake_transform)
        assert fake_transform.status == TransformStatus.running
        assert fake_transform.finish_time is None

    @pytest.mark.parametrize(
        "status",
        [TransformStatus.complete, TransformStatus.fatal, TransformStatus.canceled],
    )
    def test_complete(
        self, http_method, client, fake_transform, status: TransformStatus
    ):
        fake_transform.status = status
        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 400
        assert "not in progress" in resp.json["message"]

    def test_404(self, http_method, client):
        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 404
        assert "Transformation request not found" in resp.json["message"]
