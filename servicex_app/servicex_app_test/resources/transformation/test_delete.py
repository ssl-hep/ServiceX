from unittest.mock import MagicMock

import pytest

from servicex_app.models import TransformRequest, TransformStatus
from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformDelete(ResourceTestBase):
    module = "servicex_app.resources.transformation.delete"

    @pytest.fixture
    def mock_object_store_manager(self, mocker) -> MagicMock:
        return mocker.MagicMock()

    @pytest.fixture
    def fake_transform(self, mocker) -> TransformRequest:
        mock_transform_request_cls = mocker.patch(f"{self.module}.TransformRequest")
        transform = self._generate_transform_request()
        mock_transform_request_cls.lookup.return_value = transform
        return transform

    @pytest.fixture
    def db_session(self, mocker):
        mock_db = mocker.patch(f"{self.module}.db")
        mock_db.session = mocker.MagicMock()
        return mock_db.session

    def test_delete(self, fake_transform, db_session, mock_object_store_manager):
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
        db_session.delete.assert_called_once_with(fake_transform)
        db_session.query().filter_by.assert_called_once_with(request_id="BR549")
        db_session.query().filter_by.return_value.delete.assert_called_once_with()
        mock_object_store_manager.delete_bucket_and_contents.assert_called_once_with("BR549")

    def test_running(self, fake_transform, db_session):
        fake_transform.status = TransformStatus.running

        client = self._test_client()

        resp = client.delete("/servicex/transformation/BR549")
        assert resp.status_code == 400
        assert resp.json["message"] == "Transform request with id BR549 is still in progress."
        assert not db_session.query().filter_by.return_value.delete.called
        assert not db_session.delete.called

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
                                                db_session,
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
