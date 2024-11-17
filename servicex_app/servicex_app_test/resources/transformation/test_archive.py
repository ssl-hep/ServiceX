from unittest.mock import MagicMock

import pytest

from servicex_app.models import TransformRequest, TransformStatus
from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformArchive(ResourceTestBase):
    module = "servicex_app.resources.transformation.archive"

    @pytest.fixture
    def mock_object_store_manager(self, mocker) -> MagicMock:
        return mocker.MagicMock()

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        mock_transform_request_cls = mocker.patch(f"{self.module}.TransformRequest")
        transform = self._generate_transform_request()
        transform.save_to_db = MagicMock()
        transform.truncate_results = MagicMock()
        mock_transform_request_cls.lookup.return_value = transform
        return transform

    def test_archive(self, fake_transform, mock_object_store_manager):
        fake_transform.status = TransformStatus.complete

        local_config = {
            'OBJECT_STORE_ENABLED': True,
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1'
        }

        client = self._test_client(extra_config=local_config,
                                   object_store=mock_object_store_manager)

        resp = client.delete("/servicex/transformation/BR549")
        assert resp.status_code == 200
        assert fake_transform.archived
        assert fake_transform.save_to_db.called
        assert fake_transform.truncate_results.called
        mock_object_store_manager.delete_bucket_and_contents.assert_called_once_with("BR549")

    def test_running(self, fake_transform):
        fake_transform.status = TransformStatus.running

        client = self._test_client()

        resp = client.delete("/servicex/transformation/BR549")
        assert resp.status_code == 400
        assert resp.json["message"] == "Transform request with id BR549 is still in progress."
        assert not fake_transform.archived
        assert not fake_transform.save_to_db.called
        assert not fake_transform.truncate_results.called

    def test_already_archived(self, fake_transform):
        fake_transform.status = TransformStatus.running
        fake_transform.archived = True

        client = self._test_client()

        resp = client.delete("/servicex/transformation/BR549")
        assert resp.status_code == 404
        assert resp.json["message"] == "Transformation request with id: BR549 is already archived."
        assert fake_transform.archived
        assert not fake_transform.save_to_db.called
        assert not fake_transform.truncate_results.called

    def test_not_found(self):
        client = self._test_client()

        resp = client.delete("/servicex/transformation/BR549")
        assert resp.status_code == 404

    @pytest.mark.parametrize("user_id, submitter_id, is_admin, expected_status", [
        (42, 42, False, 200),  # Submitting user wants to delete their own request
        (42, 42, True, 200),  # Admin wants to delete their own request
        (42, 43, True, 200),  # Admin wants to delete someone else's request
        (42, 43, False, 403),  # User tries to delete someone else's request
    ])
    def test_submit_transformation_auth_enabled(self,
                                                user_id, submitter_id, is_admin,
                                                expected_status,
                                                fake_transform,
                                                mock_jwt_extended, mock_requesting_user):
        fake_transform.status = TransformStatus.complete
        client = self._test_client(extra_config={'ENABLE_AUTH': True})
        with client.application.app_context():
            mock_requesting_user.id = user_id
            mock_requesting_user.admin = is_admin
            fake_transform.submitted_by = submitter_id

            resp = client.delete("/servicex/transformation/BR549",
                                 headers=self.fake_header())

            assert resp.status_code == expected_status
