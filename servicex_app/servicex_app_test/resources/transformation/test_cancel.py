from unittest.mock import MagicMock

import kubernetes as k8s
import pytest

from servicex_app.models import TransformRequest, TransformStatus
from servicex_app.temporal_adaptor import TemporalAdaptor
from servicex_app_test.resource_test_base import ResourceTestBase

URL = "/servicex/transformation/1234/cancel"


class TestTransformCancel(ResourceTestBase):
    module = "servicex_app.resources.transformation.cancel"

    @staticmethod
    def _test_client(extra_config=None, **kwargs):
        # The Celery-era path; the Temporal one is tested below.
        config = {"ORCHESTRATOR": "celery", **(extra_config or {})}
        return ResourceTestBase._test_client(extra_config=config, **kwargs)

    @pytest.fixture(params=["get", "post"])
    def http_method(self, request):
        return request.param

    @pytest.fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_deployment_status.return_value = None
        return mock_transform_manager

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        fake = self._generate_transform_request()
        fake.save_to_db = mocker.Mock()
        mocker.patch(f"{self.module}.TransformRequest.lookup", return_value=fake)
        return fake

    def test_submitted(
        self,
        http_method,
        fake_transform,
        mock_transform_manager,
    ):
        fake_transform.status = TransformStatus.submitted
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None
        mock_transform_manager.cancel_transform.assert_called_once_with(fake_transform)

    def test_running(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
    ):
        fake_transform.status = TransformStatus.running
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        mock_transform_manager.cancel_transform.assert_called_once_with(fake_transform)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_deployment_not_found(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
    ):
        fake_transform.status = TransformStatus.running
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200
        mock_transform_manager.cancel_transform.assert_called_once_with(fake_transform)
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_running_k8s_exception(
        self,
        http_method,
        mock_transform_manager,
        fake_transform,
    ):
        fake_transform.status = TransformStatus.running
        exc = k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        mock_transform_manager.cancel_transform.side_effect = exc
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 403
        mock_transform_manager.cancel_transform.assert_called_once_with(fake_transform)
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


class TestTransformCancelTemporal(ResourceTestBase):
    module = "servicex_app.resources.transformation.cancel"

    @pytest.fixture(params=["get", "post"])
    def http_method(self, request):
        return request.param

    @pytest.fixture
    def mock_temporal(self) -> MagicMock:
        adaptor = MagicMock(TemporalAdaptor)
        adaptor.cancel_transform_request.return_value = True
        return adaptor

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        fake = self._generate_transform_request()
        fake.save_to_db = mocker.Mock()
        mocker.patch(f"{self.module}.TransformRequest.lookup", return_value=fake)
        return fake

    def _client(self, mock_temporal, transformation_manager=None):
        return self._test_client(
            extra_config={"ORCHESTRATOR": "temporal"},
            transformation_manager=transformation_manager,
            temporal_adaptor=mock_temporal,
        )

    @pytest.mark.parametrize(
        "status",
        [
            TransformStatus.submitted,
            TransformStatus.lookup,
            TransformStatus.pending_lookup,
            TransformStatus.running,
        ],
    )
    def test_cancels_workflow(
        self, http_method, mock_temporal, fake_transform, status, mocker
    ):
        fake_transform.status = status
        transform_manager = mocker.MagicMock()
        client = self._client(mock_temporal, transform_manager)

        resp = getattr(client, http_method)(URL)

        assert resp.status_code == 200
        mock_temporal.cancel_transform_request.assert_called_once_with("1234")
        transform_manager.cancel_transform.assert_not_called()
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_no_open_workflow_still_cancels(
        self, http_method, mock_temporal, fake_transform
    ):
        fake_transform.status = TransformStatus.running
        mock_temporal.cancel_transform_request.return_value = False
        client = self._client(mock_temporal)

        resp = getattr(client, http_method)(URL)

        assert resp.status_code == 200
        assert fake_transform.status == TransformStatus.canceled
        assert fake_transform.finish_time is not None

    def test_temporal_error_leaves_request_alone(
        self, http_method, mock_temporal, fake_transform
    ):
        fake_transform.status = TransformStatus.running
        mock_temporal.cancel_transform_request.side_effect = RuntimeError("unreachable")
        client = self._client(mock_temporal)

        resp = getattr(client, http_method)(URL)

        assert resp.status_code == 503
        assert "unreachable" in resp.json["message"]
        assert fake_transform.status == TransformStatus.running
        assert fake_transform.finish_time is None
        fake_transform.save_to_db.assert_not_called()

    def test_complete_is_not_sent_to_temporal(
        self, http_method, mock_temporal, fake_transform
    ):
        fake_transform.status = TransformStatus.complete
        client = self._client(mock_temporal)

        resp = getattr(client, http_method)(URL)

        assert resp.status_code == 400
        mock_temporal.cancel_transform_request.assert_not_called()
