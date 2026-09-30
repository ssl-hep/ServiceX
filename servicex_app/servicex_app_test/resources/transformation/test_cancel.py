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
    def fake_transform(self, mocker) -> TransformRequest:
        fake = self._generate_transform_request()
        fake.save_to_db = mocker.Mock()
        mocker.patch("servicex_app.models.TransformRequest.lookup", return_value=fake)
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

    def test_auth_disabled(self, http_method, fake_transform, mock_transform_manager):
        fake_transform.status = TransformStatus.running
        fake_transform.submitted_by = 43
        client = self._test_client(transformation_manager=mock_transform_manager)

        resp = getattr(client, http_method)(URL)
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "user_id, submitter_id, is_admin, expected_status",
        [
            (42, 42, False, 200),  # Owner cancels their own request
            (42, 43, True, 200),  # Admin cancels someone else's request
            (42, 43, False, 403),  # User tries to cancel someone else's request
        ],
    )
    def test_ownership(
        self,
        http_method,
        user_id,
        submitter_id,
        is_admin,
        expected_status,
        fake_transform,
        mock_transform_manager,
        mock_jwt_extended,
        mock_requesting_user,
    ):
        fake_transform.status = TransformStatus.running
        client = self._test_client(
            extra_config={"ENABLE_AUTH": True},
            transformation_manager=mock_transform_manager,
        )
        with client.application.app_context():
            mock_requesting_user.id = user_id
            mock_requesting_user.admin = is_admin
            fake_transform.submitted_by = submitter_id

            resp = getattr(client, http_method)(URL, headers=self.fake_header())

            assert resp.status_code == expected_status
