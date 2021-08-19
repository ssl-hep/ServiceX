# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from tests.resource_test_base import ResourceTestBase


class TestTransformStatus(ResourceTestBase):
    def test_post_status(self, mocker, client):
        from servicex.models import TransformRequest
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mocker.patch.object(
            TransformRequest,
            'return_request',
            return_value=mock_request)

        response = client.post('/servicex/internal/transformation/1234/status',
                               json={
                                   'timestamp': '2019-09-18T16:15:09.457481',
                                   'severity': "info",
                                   'info': 'Just testing'
                               })

        assert response.status_code == 200
        mock_request.save_to_db.assert_not_called()

    def test_post_status_fatal(self, mocker, client):
        from servicex.models import TransformRequest
        mock_request = self._generate_transform_request()
        mock_request.save_to_db = mocker.Mock()
        mocker.patch.object(
            TransformRequest,
            'return_request',
            return_value=mock_request)

        response = client.post('/servicex/internal/transformation/1234/status',
                               json={
                                   'timestamp': '2019-09-18T16:15:09.457481',
                                   'severity': "fatal",
                                   'info': 'Just testing'
                               })

        assert response.status_code == 200
        assert mock_request.finish_time is not None
        mock_request.save_to_db.assert_called()

    def test_post_status_bad_data(self, client):
        response = client.post('/servicex/internal/transformation/1234/status',
                               json={'foo': 'bar'})
        assert response.status_code == 400

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
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=fake_transform_request
        )

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 200
        assert response.json == {
            "status": fake_transform_request.status,
            'request-id': "1234",
            "submit-time": fake_transform_request.submit_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finish-time": fake_transform_request.finish_time,
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
            'return_request',
            return_value=None)

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with("1234")
