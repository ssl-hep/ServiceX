from unittest.mock import MagicMock, call

import kubernetes as k8s
import pytest

from servicex_app.models import TransformStatus
from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app_test.resource_test_base import ResourceTestBase


class TestCancelAllTransform(ResourceTestBase):
    module = "servicex_app.resources.transformation.cancel_all"

    @pytest.fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        return mocker.MagicMock()

    @pytest.fixture
    def mock_transform_request_cls(self, mocker):
        return mocker.patch(f"{self.module}.TransformRequest")

    @pytest.fixture
    def client(self, mock_jwt_extended, mock_requesting_user, mock_transform_manager):
        return self._test_client(
            transformation_manager=mock_transform_manager,
            extra_config={"ENABLE_AUTH": True},
        )

    def _setup_query(self, mock_cls, transforms, mocker, mock_transform_manager):
        mock_transform_manager.shutdown_pod = mocker.Mock()
        mock_cls.active_user_transformations.return_value = transforms

    @pytest.mark.parametrize(
        "status",
        [TransformStatus.submitted, TransformStatus.running, TransformStatus.lookup],
    )
    def test_cancels_transform(
        self,
        client,
        mock_transform_manager,
        mock_transform_request_cls,
        mocker,
        status,
    ):
        fake = self._generate_transform_request()
        fake.status = status
        self._setup_query(mock_transform_request_cls, [fake], mocker, mock_transform_manager)

        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert fake.request_id in resp.json["canceled"]
        assert fake.status == TransformStatus.canceled
        assert fake.finish_time is not None
        mock_transform_manager.shutdown_pod.assert_called_once_with(fake)

    def test_cancels_multiple_transforms(
        self, client, mock_transform_manager, mock_transform_request_cls, mocker
    ):
        t1 = self._generate_transform_request()
        t1.request_id = "aaa-111"
        t1.status = TransformStatus.submitted
        t2 = self._generate_transform_request()
        t2.request_id = "bbb-222"
        t2.status = TransformStatus.running
        self._setup_query(mock_transform_request_cls, [t1, t2], mocker, mock_transform_manager)

        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert set(resp.json["canceled"]) == {"aaa-111", "bbb-222"}
        assert t1.status == TransformStatus.canceled
        assert t2.status == TransformStatus.canceled
        mock_transform_manager.shutdown_pod.assert_has_calls([call(t1), call(t2)])

    def test_no_active_transforms(
        self, client, mock_transform_manager, mock_transform_request_cls, mocker
    ):
        self._setup_query(mock_transform_request_cls, [], mocker, mock_transform_manager)

        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert resp.json["canceled"] == []

    def test_k8s_error_still_cancels(
        self, client, mock_transform_manager, mock_transform_request_cls, mocker
    ):
        fake = self._generate_transform_request()
        fake.status = TransformStatus.running
        self._setup_query(mock_transform_request_cls, [fake], mocker, mock_transform_manager)
        mock_transform_manager.shutdown_pod.side_effect = k8s.client.exceptions.ApiException(status=404)

        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert fake.request_id in resp.json["canceled"]
        assert fake.status == TransformStatus.canceled

    def test_shutdown_error_continues_to_next_transform(
        self, client, mock_transform_manager, mock_transform_request_cls, mocker
    ):
        t1 = self._generate_transform_request()
        t1.request_id = "aaa-111"
        t1.status = TransformStatus.running
        t2 = self._generate_transform_request()
        t2.request_id = "bbb-222"
        t2.status = TransformStatus.submitted
        self._setup_query(mock_transform_request_cls, [t1, t2], mocker, mock_transform_manager)
        exc = k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        mock_transform_manager.shutdown_pod.side_effect = exc

        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert set(resp.json["canceled"]) == {"aaa-111", "bbb-222"}
        assert t1.status == TransformStatus.canceled
        assert t2.status == TransformStatus.canceled

    def test_auth_enabled_queries_by_user(
        self,
        mock_jwt_extended,
        mock_requesting_user,
        mock_transform_manager,
        mock_transform_request_cls,
        mocker,
    ):
        client = self._test_client(
            transformation_manager=mock_transform_manager,
            extra_config={"ENABLE_AUTH": True},
        )
        self._setup_query(mock_transform_request_cls, [], mocker, mock_transform_manager)
        with client.application.app_context():
            client.post(
                "/servicex/transformation/cancel-all",
                headers=self.fake_header(),
            )

        mock_transform_request_cls.active_user_transformations.assert_called_once_with(
            mock_requesting_user
        )

    def test_auth_disabled(
        self,
        mock_jwt_extended,
        mock_requesting_user,
        mock_transform_manager,
        mock_transform_request_cls,
        mocker,
    ):
        client = self._test_client(
            transformation_manager=mock_transform_manager,
            extra_config={"ENABLE_AUTH": False},
        )
        self._setup_query(mock_transform_request_cls, [], mocker, mock_transform_manager)
        with client.application.app_context():
            response = client.post(
                "/servicex/transformation/cancel-all",
                headers=self.fake_header(),
            )
            assert response.status_code == 400

    def test_no_user_found(
        self,
        mock_jwt_extended,
        mock_requesting_user,
        mock_transform_manager,
        mock_transform_request_cls,
        mocker,
    ):
        mocker.patch.object(ServiceXResource, "get_requesting_user", return_value=None)
        client = self._test_client(
            transformation_manager=mock_transform_manager,
            extra_config={"ENABLE_AUTH": True},
        )
        self._setup_query(mock_transform_request_cls, [], mocker, mock_transform_manager)
        with client.application.app_context():
            resp = client.post(
                "/servicex/transformation/cancel-all",
                headers=self.fake_header(),
            )
        assert resp.status_code == 400
        assert resp.json["message"] == "No user found"
