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
from servicex import LookupResultProcessor
from tests.resource_test_base import ResourceTestBase


class TestAddFileToDataset(ResourceTestBase):
    def test_put_new_file(self, mocker):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/1234/files',
                              json={
                                  'paths': ["/foo/bar1.root", "/foo/bar2.root"],
                                  'adler32': '12345',
                                  'file_size': 1024,
                                  'file_events': 500
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_processor.add_file_to_dataset.assert_called()
        assert response.json == {
            "request-id": '1234'
        }

    def test_put_new_file_bulk(self, mocker):
        import servicex
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/1234/files',
                              json=[
                                  {
                                      'paths': ["/foo/bar1.root", "/foo/bar2.root"],
                                      'adler32': '12345',
                                      'file_size': 1024,
                                      'file_events': 500
                                  },
                                  {
                                      'paths': ["/foo1/bar1.root", "/foo1/bar2.root"],
                                      'adler32': '12345',
                                      'file_size': 2048,
                                      'file_events': 500
                                  }
                              ])
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_processor.add_file_to_dataset.assert_called()
        assert response.json == {
            "request-id": '1234'
        }

    def test_put_new_file_root_dest(self, mocker):
        import servicex

        root_file_transform_request = self._generate_transform_request()
        root_file_transform_request.result_destination = 'root'

        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=root_file_transform_request)

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)
        response = client.put('/servicex/internal/transformation/1234/files',
                              json={
                                  'paths': ["/foo/bar1.root", "/foo/bar2.root"],
                                  'adler32': '12345',
                                  'file_size': 1024,
                                  'file_events': 500
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_processor.add_file_to_dataset.assert_called()

        assert response.json == {
            "request-id": '1234'
        }

    def test_put_new_file_with_exception(self, mocker):
        import servicex
        mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_processor.add_file_to_dataset.side_effect = Exception('Test')

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/1234/files',
                              json={
                                  'paths': [123, 123],
                                  'adler32': '12345',
                                  'file_size': 1024,
                                  'file_events': 500
                              })
        assert response.status_code == 500
        assert response.json == {
            'message': 'Something went wrong: sequence item 0: expected str instance, int found'}
