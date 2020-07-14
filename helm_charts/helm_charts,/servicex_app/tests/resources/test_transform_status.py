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
    def test_post_status(self, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        response = client.post('/servicex/internal/transformation/1234/status',
                               json={
                                   'timestamp': '2019-09-18T16:15:09.457481',
                                   'status': 'Just testing'
                               })

        assert response.status_code == 200

    def test_post_status_bad_data(self, mock_rabbit_adaptor):
        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)
        response = client.post('/servicex/internal/transformation/1234/status',
                               json={'foo': 'bar'})

        assert response.status_code == 400

    def test_get_status(self, mocker, mock_rabbit_adaptor):
        import servicex

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=self._generate_transform_request())

        mock_count = mocker.patch.object(
            servicex.models.TransformationResult, 'count', return_value=17)

        mock_statistics = mocker.patch.object(
            servicex.models.TransformationResult, 'statistics', return_value={
                "total-messages": 123,
                "min-time": 1,
                "max-time": 30,
                "avg-time": 15.55,
                "total-time": 1024
            })

        mock_files_remaining = mocker.patch.object(
            servicex.models.TransformRequest, 'files_remaining', return_value=12)

        mock_files_failed = mocker.patch.object(
            servicex.models.TransformationResult, 'failed_files', return_value=2)

        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 200
        assert response.json == {
            'request-id': '1234',
            'files-processed': 15,
            'files-remaining': 12,
            'files-skipped': 2,
            'stats': {
                'total-messages': 123,
                'min-time': 1,
                'max-time': 30,
                'avg-time': 15.55,
                'total-time': 1024}
        }
        mock_transform_request_read.assert_called_with("1234")
        mock_count.assert_called_with('1234')
        mock_files_remaining.assert_called_with('1234')
        mock_statistics.assert_called_with('1234')
        mock_files_failed.assert_called_with('1234')

    def test_get_status_bad_request_id(self, mocker, mock_rabbit_adaptor):
        import servicex

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=None)

        client = self._test_client(rabbit_adaptor=mock_rabbit_adaptor)

        response = client.get('/servicex/transformation/1234/status')
        assert response.status_code == 404
        mock_transform_request_read.assert_called_with("1234")
