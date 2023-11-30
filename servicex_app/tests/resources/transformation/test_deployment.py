from unittest.mock import MagicMock

from pytest import fixture

from tests.resource_test_base import ResourceTestBase


class TestDeploymentStatus(ResourceTestBase):
    module = "servicex.resources.transformation.deployment"

    @fixture
    def mock_transform_manager(self, mocker) -> MagicMock:
        mock_transform_manager = mocker.MagicMock()
        mock_transform_manager.get_deployment_status.return_value = None
        return mock_transform_manager

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
            self, mock_transform_manager, mock_deployment_status
    ):
        mock_transform_manager.get_deployment_status.return_value = mock_deployment_status

        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/deployment-status")
        assert response.status_code == 200
        assert response.json == mock_deployment_status.to_dict.return_value

    def test_deployment_status_404(self, mock_transform_manager):
        client = self._test_client(transformation_manager=mock_transform_manager)
        response = client.get("/servicex/transformation/1234/deployment-status")
        assert response.status_code == 404
