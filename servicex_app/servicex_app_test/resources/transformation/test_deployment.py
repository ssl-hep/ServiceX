from unittest.mock import MagicMock

import pytest
from pytest import fixture

from servicex_app_test.resource_test_base import ResourceTestBase


class TestDeploymentStatus(ResourceTestBase):
    module = "servicex_app.resources.transformation.deployment"

    @fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_deployment_status.return_value = None
        return mock_transform_manager

    @fixture
    def fake_transform(self, mocker):
        transform = self._generate_transform_request()
        mocker.patch(
            "servicex_app.models.TransformRequest.lookup", return_value=transform
        )
        return transform

    @fixture
    def mock_deployment_status(self) -> MagicMock:
        mock_deployment_status = MagicMock()
        mock_deployment_status.to_dict.return_value = {
            "available_replicas": 1,
            "collision_count": None,
            "observed_generation": 19,
            "ready_replicas": 1,
            "replicas": 1,
            "unavailable_replicas": None,
            "updated_replicas": 1,
        }
        return mock_deployment_status

    def test_deployment_status(
        self, mock_transform_manager, mock_deployment_status, fake_transform
    ):
        mock_transform_manager.get_deployment_status.return_value = (
            mock_deployment_status
        )

        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/deployment-status")
        assert response.status_code == 200
        assert response.json == mock_deployment_status.to_dict.return_value

    def test_deployment_status_404(self, mock_transform_manager, fake_transform):
        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/deployment-status")
        assert response.status_code == 404

    def test_deployment_status_request_not_found(self, mock_transform_manager):
        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/deployment-status")
        assert response.status_code == 404
        assert "Transformation request not found" in response.json["message"]
        mock_transform_manager.get_deployment_status.assert_not_called()

    @pytest.mark.parametrize(
        "user_id, submitter_id, is_admin, expected_status",
        [
            (42, 42, False, 200),  # Owner reads their own deployment
            (42, 43, True, 200),  # Admin reads someone else's deployment
            (42, 43, False, 403),  # User tries to read someone else's deployment
        ],
    )
    def test_deployment_status_ownership(
        self,
        user_id,
        submitter_id,
        is_admin,
        expected_status,
        mock_transform_manager,
        mock_deployment_status,
        fake_transform,
        mock_jwt_extended,
        mock_requesting_user,
    ):
        mock_transform_manager.get_deployment_status.return_value = (
            mock_deployment_status
        )
        fake_transform.submitted_by = submitter_id
        client = self._test_client(
            extra_config={"ENABLE_AUTH": True},
            transformation_manager=mock_transform_manager,
        )
        with client.application.app_context():
            mock_requesting_user.id = user_id
            mock_requesting_user.admin = is_admin
            response = client.get(
                "/servicex/transformation/1234/deployment-status",
                headers=self.fake_header(),
            )
            assert response.status_code == expected_status
