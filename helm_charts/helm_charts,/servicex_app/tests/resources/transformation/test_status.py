from datetime import datetime

from tests.resource_test_base import ResourceTestBase


class TestTransformStatus(ResourceTestBase):
    def test_get_status(self, mocker, client):
        import servicex

        mock_files_processed = mocker.PropertyMock(return_value=15)
        servicex.models.TransformRequest.files_processed = mock_files_processed
        mock_files_remaining = mocker.PropertyMock(return_value=12)
        servicex.models.TransformRequest.files_remaining = mock_files_remaining
        mock_files_failed = mocker.PropertyMock(return_value=2)
        servicex.models.TransformRequest.files_failed = mock_files_failed
        mock_statistics = mocker.PropertyMock(return_value={
            "total-messages": 123,
            "min-time": 1,
            "max-time": 30,
            "avg-time": 15.55,
            "total-time": 1024
        })
        servicex.models.TransformRequest.statistics = mock_statistics

        fake_transform_request = self._generate_transform_request()
        fake_transform_request.finish_time = datetime.max
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=fake_transform_request
        )

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 200
        iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
        assert response.json == {
            "status": fake_transform_request.status,
            'request-id': "1234",
            "submit-time": fake_transform_request.submit_time.strftime(iso_fmt),
            "finish-time": fake_transform_request.finish_time.strftime(iso_fmt),
            'files-processed': mock_files_processed.return_value,
            'files-remaining': mock_files_remaining.return_value,
            'files-skipped': mock_files_failed.return_value,
            'stats': {
                'total-messages': 123,
                'min-time': 1,
                'max-time': 30,
                'avg-time': 15.55,
                'total-time': 1024}
        }
        mock_transform_request_read.assert_called_with("1234")

    def test_get_status_404(self, mocker, client):
        import servicex

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=None)

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with("1234")
