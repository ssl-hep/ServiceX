from unittest.mock import patch

from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformationRequest(ResourceTestBase):

    def test_get_single_request_no_object_store(self, mocker):
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            fake_transform_request = self._generate_transform_request()
            mock_lookup.return_value = fake_transform_request

            client = self._test_client(
                extra_config={
                    "OBJECT_STORE_ENABLED": False,
                    "LOGS_URL": "https://log.servicex.com",
                }
            )
            response = client.get("/servicex/transformation/1234")
        assert response.status_code == 200
        assert response.json["log-url"] == "https://log.servicex.com"
        assert response.json["title"] == "Test Transformation"
        transform = response.json

        assert transform["request_id"] == "BR549"
        mock_lookup.assert_called_with("1234")

    def test_get_single_request_with_object_store(self, mocker):
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            fake_transform_request = self._generate_transform_request()
            fake_transform_request.result_destination = "object-store"
            mock_lookup.return_value = fake_transform_request

            local_config = {
                "OBJECT_STORE_ENABLED": True,
                "MINIO_PUBLIC_URL": "minio.servicex.com:9000",
                "MINIO_ENCRYPT": True,
                "MINIO_ACCESS_KEY": "miniouser",
                "MINIO_SECRET_KEY": "leftfoot1",
            }

            client = self._test_client(extra_config=local_config)
            response = client.get("/servicex/transformation/1234")
        assert response.status_code == 200
        transform = response.json
        assert transform["request_id"] == "BR549"
        mock_lookup.assert_called_with("1234")

    def test_get_single_request_with_webdav(self, mocker):
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            fake_transform_request = self._generate_transform_request()
            fake_transform_request.result_destination = "webdav"
            mock_lookup.return_value = fake_transform_request

            local_config = {
                "OBJECT_STORE_ENABLED": False,
                "WEBDAV_ENABLED": True,
                "WEBDAV_PUBLIC_URL": "https://webdav.servicex.com/",
                "WEBDAV_ROOT": "servicex",
                "WEBDAV_USERNAME": "servicex",
                "WEBDAV_PASSWORD": "leftfoot1",
            }

            client = self._test_client(extra_config=local_config)
            response = client.get("/servicex/transformation/1234")
        assert response.status_code == 200
        transform = response.json
        assert (
            transform["webdav-endpoint"] == "https://webdav.servicex.com/servicex/BR549"
        )
        assert transform["webdav-username"] == "servicex"
        assert transform["webdav-password"] == "leftfoot1"

    def test_get_single_request_webdav_not_deployed(self, mocker):
        """A transform written to webdav on an instance that no longer has one."""
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            fake_transform_request = self._generate_transform_request()
            fake_transform_request.result_destination = "webdav"
            mock_lookup.return_value = fake_transform_request

            client = self._test_client(extra_config={"OBJECT_STORE_ENABLED": False})
            response = client.get("/servicex/transformation/1234")
        assert response.status_code == 200
        assert "webdav-endpoint" not in response.json

    def test_get_single_request_404(self, mocker, client):
        with patch("servicex_app.models.TransformRequest.lookup") as mock_lookup:
            mock_lookup.return_value = None
            response = client.get("/servicex/transformation/1234")
        assert response.status_code == 404
        mock_lookup.assert_called_with("1234")
