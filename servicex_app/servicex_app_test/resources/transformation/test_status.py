from datetime import datetime
from unittest.mock import patch, PropertyMock

from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformStatus(ResourceTestBase):
    def test_get_status(self, mocker, client):
        with patch('servicex_app.models.TransformRequest.lookup') as mock_lookup:
            with patch('servicex_app.models.TransformRequest.statistics', new_callable=PropertyMock) as mock_stats:
                # Set up the mock to return a specific value
                fake_transform_request = self._generate_transform_request()
                fake_transform_request.submit_time = datetime(2021, 1, 1, 12, 0, 0)
                fake_transform_request.finish_time = datetime(2021, 1, 1, 12, 30, 0)
                fake_transform_request.files = 32
                fake_transform_request.files_completed = 15
                fake_transform_request.files_failed = 2

                mock_stats.return_value = {
                    'min-time': 1,
                    'max-time': 30,
                    'avg-time': 15.55,
                    'total-time': 1024}

                mock_lookup.return_value = fake_transform_request
                response = client.get('/servicex/transformation/1234/status')
            assert response.status_code == 200
            iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
            assert response.json == {
                "status": fake_transform_request.status.string_name,
                'request-id': "1234",
                "submit-time": fake_transform_request.submit_time.strftime(iso_fmt),
                "finish-time": fake_transform_request.finish_time.strftime(iso_fmt),
                'files-completed': 15,
                'files-processed': 15,
                'files-remaining': 15,
                'files-failed': 2,
                'files-skipped': 2,
                'stats': {
                    'min-time': 1,
                    'max-time': 30,
                    'avg-time': 15.55,
                    'total-time': 1024}
            }

    def test_get_status_404(self, mocker, client):
        import servicex_app

        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest,
            'lookup',
            return_value=None)

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with("1234")
