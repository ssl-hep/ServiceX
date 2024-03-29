from tests.resource_test_base import ResourceTestBase


class TestTransformationRequest(ResourceTestBase):

    def test_get_single_request_no_object_store(self, mocker):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())
        client = self._test_client(extra_config={'OBJECT_STORE_ENABLED': False})
        response = client.get('/servicex/transformation/1234')
        assert response.status_code == 200
        transform = response.json

        assert transform['request_id'] == 'BR549'
        mock_transform_request_read.assert_called_with('1234')

    def test_get_single_request_with_object_store(self, mocker):
        import servicex
        object_store_transform_request = self._generate_transform_request()
        object_store_transform_request.result_destination = 'object-store'
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=object_store_transform_request)

        local_config = {
            'OBJECT_STORE_ENABLED': True,
            'MINIO_PUBLIC_URL': 'minio.servicex.com:9000',
            'MINIO_ENCRYPT': True,
            'MINIO_ACCESS_KEY': 'miniouser',
            'MINIO_SECRET_KEY': 'leftfoot1'
        }

        client = self._test_client(extra_config=local_config)
        response = client.get('/servicex/transformation/1234')
        assert response.status_code == 200
        transform = response.json
        assert transform['request_id'] == 'BR549'
        mock_transform_request_read.assert_called_with('1234')

    def test_get_single_request_404(self, mocker, client):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest, 'lookup',
            return_value=None)
        response = client.get('/servicex/transformation/1234')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with('1234')
