from pytest import fixture
from servicex_app.code_gen_adapter import CodeGenAdapter
from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformationResults(ResourceTestBase):
    @staticmethod
    def _generate_transformation_request(**kwargs):
        request = {
            'did': '123-45-678',
            'selection': "test-string",
            'result-destination': 'object-store',
            'result-format': 'root-file',
            'workers': 10,
            'codegen': 'atlasxaod'
        }
        request.update(kwargs)
        return request

    @fixture
    def mock_codegen(self, mocker):
        mock_code_gen = mocker.MagicMock(CodeGenAdapter)
        mock_code_gen.generate_code_for_selection.return_value = (
            'my-cm',
            'ssl-hep/func_adl:latest',
            'bash', 'echo'
        )
        return mock_code_gen

    def test_get_status(
            self,
            mock_rabbit_adaptor,
            mock_codegen,
            mock_celery_app,
    ):
        client = self._test_client(
            rabbit_adaptor=mock_rabbit_adaptor,
            code_gen_service=mock_codegen,
            celery_app=mock_celery_app
        )
        request = self._generate_transformation_request()

        create_transformation_response = client.post(
            '/servicex/transformation',
            json=request,
        )
        assert create_transformation_response.status_code == 200
        assert 'request_id' in create_transformation_response.json
        request_id = create_transformation_response.json['request_id']
        assert isinstance(request_id, str)
        transformation_results_response = client.get(f'/servicex/transformation/{request_id}/results')
        assert transformation_results_response.status_code == 200
