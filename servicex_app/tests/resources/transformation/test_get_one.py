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
        assert response.json == {'request_id': 'BR549', 'did': '123-456-789',
                                 'columns': 'electron.eta(), muon.pt()',
                                 'selection': None,
                                 'tree-name': "Events",
                                 'image': 'ssl-hep/foo:latest',
                                 'workers': 42,
                                 'result-destination': None,
                                 'result-format': 'arrow',
                                 'workflow-name': None,
                                 'generated-code-cm': None,
                                 'status': "Submitted",
                                 'failure-info': None,
                                 'app-version': "1.0.1",
                                 'code-gen-image': 'sslhep/servicex_code_gen_func_adl_xaod:develop'
                                 }
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
        print(response.json)
        assert response.json == {'request_id': 'BR549', 'did': '123-456-789',
                                 'columns': 'electron.eta(), muon.pt()',
                                 'selection': None,
                                 'tree-name': "Events",
                                 'image': 'ssl-hep/foo:latest',
                                 'workers': 42,
                                 'result-destination': 'object-store',
                                 'result-format': 'arrow',
                                 'minio-endpoint': 'minio.servicex.com:9000',
                                 'minio-secured': True,
                                 'minio-access-key': 'miniouser',
                                 'minio-secret-key': 'leftfoot1',
                                 'workflow-name': None,
                                 'generated-code-cm': None,
                                 'status': "Submitted",
                                 'failure-info': None,
                                 'app-version': "1.0.1",
                                 'code-gen-image': 'sslhep/servicex_code_gen_func_adl_xaod:develop'
                                 }

        mock_transform_request_read.assert_called_with('1234')

    def test_get_single_request_404(self, mocker, client):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest, 'lookup',
            return_value=None)
        response = client.get('/servicex/transformation/1234')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with('1234')
