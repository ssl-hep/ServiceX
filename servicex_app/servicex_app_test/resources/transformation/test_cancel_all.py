from unittest.mock import MagicMock

import kubernetes as k8s
import pytest

from servicex_app.models import TransformStatus
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

    def _setup_query(self, mock_cls, transforms):
        mock_cls.query.filter.return_value.all.return_value = transforms

    @pytest.mark.parametrize(
        "status,expect_shutdown",
        [
            (TransformStatus.submitted, False),
            (TransformStatus.running, True),
            (TransformStatus.lookup, True),
        ],
    )
    def test_cancels_transform(
        self,
        client,
        mock_transform_manager,
        mock_transform_request_cls,
        status,
        expect_shutdown,
    ):
        fake = self._generate_transform_request()
        fake.status = status
        self._setup_query(mock_transform_request_cls, [fake])

        with client.application.app_context():
            resp = client.get(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert fake.request_id in resp.json["canceled"]
        assert fake.status == TransformStatus.canceled
        assert fake.finish_time is not None
        if expect_shutdown:
            mock_transform_manager.shutdown_transformer_job.assert_called_once_with(
                fake.request_id, client.application.config["TRANSFORMER_NAMESPACE"]
            )
        else:
            mock_transform_manager.shutdown_transformer_job.assert_not_called()

    def test_cancels_multiple_transforms(
        self, client, mock_transform_manager, mock_transform_request_cls
    ):
        t1 = self._generate_transform_request()
        t1.request_id = "aaa-111"
        t1.status = TransformStatus.submitted
        t2 = self._generate_transform_request()
        t2.request_id = "bbb-222"
        t2.status = TransformStatus.running
        self._setup_query(mock_transform_request_cls, [t1, t2])

        with client.application.app_context():
            resp = client.get(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert set(resp.json["canceled"]) == {"aaa-111", "bbb-222"}
        assert t1.status == TransformStatus.canceled
        assert t2.status == TransformStatus.canceled
        mock_transform_manager.shutdown_transformer_job.assert_called_once_with(
            "bbb-222", client.application.config["TRANSFORMER_NAMESPACE"]
        )

    def test_no_active_transforms(
        self, client, mock_transform_manager, mock_transform_request_cls
    ):
        self._setup_query(mock_transform_request_cls, [])

        with client.application.app_context():
            resp = client.get(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert resp.json["canceled"] == []
        mock_transform_manager.shutdown_transformer_job.assert_not_called()

    def test_k8s_404_still_cancels(
        self, client, mock_transform_manager, mock_transform_request_cls
    ):
        fake = self._generate_transform_request()
        fake.status = TransformStatus.running
        mock_transform_manager.shutdown_transformer_job.side_effect = (
            k8s.client.exceptions.ApiException(status=404)
        )
        self._setup_query(mock_transform_request_cls, [fake])

        with client.application.app_context():
            resp = client.get(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert fake.request_id in resp.json["canceled"]
        assert fake.status == TransformStatus.canceled

    def test_k8s_error_logs_and_continues(
        self, mocker, client, mock_transform_manager, mock_transform_request_cls
    ):
        t1 = self._generate_transform_request()
        t1.request_id = "aaa-111"
        t1.status = TransformStatus.running
        t2 = self._generate_transform_request()
        t2.request_id = "bbb-222"
        t2.status = TransformStatus.submitted
        mock_transform_manager.shutdown_transformer_job.side_effect = (
            k8s.client.exceptions.ApiException(status=403, reason="Forbidden")
        )
        self._setup_query(mock_transform_request_cls, [t1, t2])
        mock_error = mocker.patch.object(client.application.logger, "error")

        with client.application.app_context():
            resp = client.get(
                "/servicex/transformation/cancel-all", headers=self.fake_header()
            )

        assert resp.status_code == 200
        assert set(resp.json["canceled"]) == {"aaa-111", "bbb-222"}
        assert t1.status == TransformStatus.canceled
        assert t2.status == TransformStatus.canceled
        mock_error.assert_called_once()

    @pytest.mark.parametrize(
        "extra_config,expected_filter_arg_count",
        [
            ({}, 1),
            ({"ENABLE_AUTH": True}, 2),
        ],
    )
    def test_query_filter_reflects_auth_config(
        self,
        mock_jwt_extended,
        mock_requesting_user,
        mock_transform_manager,
        mock_transform_request_cls,
        extra_config,
        expected_filter_arg_count,
    ):
        client = self._test_client(
            transformation_manager=mock_transform_manager,
            extra_config=extra_config,
        )
        self._setup_query(mock_transform_request_cls, [])
        with client.application.app_context():
            client.get(
                "/servicex/transformation/cancel-all",
                headers=self.fake_header(),
            )

        call_args = mock_transform_request_cls.query.filter.call_args[0]
        assert len(call_args) == expected_filter_arg_count
