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


class TestPreflightCheck(ResourceTestBase):
    def test_post_preflight_check(self, mocker):
        import servicex
        from servicex.lookup_result_processor import LookupResultProcessor

        submitted_request = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=submitted_request)

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)
        response = client.post('/servicex/internal/transformation/1234/preflight',
                               json={'file_path': '/foo/bar.root'})
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_processor.publish_preflight_request.assert_called_with(
            submitted_request,
            '/foo/bar.root'
        )

        assert response.json == {
            "request-id": '1234',
            "file-id": 42
        }

    def test_preflight_check_with_exception(self, mocker):
        import servicex
        from servicex.lookup_result_processor import LookupResultProcessor

        submitted_request = self._generate_transform_request()

        mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=submitted_request)

        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_processor.publish_preflight_request.side_effect = Exception('Test')

        client = self._test_client(lookup_result_processor=mock_processor)
        response = client.post('/servicex/internal/transformation/1234/preflight',
                               json={'file_path': '/foo/bar.root'})
        assert response.status_code == 500
        assert response.json == {'message': 'Something went wrong'}
