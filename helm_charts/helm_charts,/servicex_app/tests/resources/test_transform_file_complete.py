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
from servicex import TransformerManager
from servicex.models import TransformRequest
from tests.resource_test_base import ResourceTestBase


class TestTransformFileComplete(ResourceTestBase):
    def test_put_transform_file_complete_files_remaining(self, mocker,  mock_rabbit_adaptor):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=self._generate_transform_request())

        mock_files_remaining = mocker.patch.object(TransformRequest, 'files_remaining',
                                                   return_value=1)

        client = self._test_client(transformation_manager=mock_transformer_manager,
                                   rabbit_adaptor=mock_rabbit_adaptor)
        response = client.put('/servicex/transformation/1234/file-complete',
                              json={
                                  'file-path': '/foo/bar.root',
                                  'status': 'OK',
                                  'total-time': 100,
                                  'num-messages': 1024
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_files_remaining.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_no_files_remaining(self, mocker,  mock_rabbit_adaptor):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=self._generate_transform_request())

        mock_files_remaining = mocker.patch.object(TransformRequest, 'files_remaining',
                                                   return_value=0)

        client = self._test_client(transformation_manager=mock_transformer_manager,
                                   rabbit_adaptor=mock_rabbit_adaptor)
        response = client.put('/servicex/transformation/1234/file-complete',
                              json={
                                  'file-path': '/foo/bar.root',
                                  'status': 'OK',
                                  'total-time': 100,
                                  'num-messages': 1024
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_files_remaining.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_called_with('1234', 'my-ws')

    def test_put_transform_file_complete_unknown_files_remaining(self, mocker,
                                                                 mock_rabbit_adaptor):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'return_request',
            return_value=self._generate_transform_request())

        mock_files_remaining = mocker.patch.object(TransformRequest, 'files_remaining',
                                                   return_value=None)

        client = self._test_client(transformation_manager=mock_transformer_manager,
                                   rabbit_adaptor=mock_rabbit_adaptor)
        response = client.put('/servicex/transformation/1234/file-complete',
                              json={
                                  'file-path': '/foo/bar.root',
                                  'status': 'OK',
                                  'total-time': 100,
                                  'num-messages': 1024
                              })
        assert response.status_code == 200
        mock_transform_request_read.assert_called_with('1234')
        mock_files_remaining.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
