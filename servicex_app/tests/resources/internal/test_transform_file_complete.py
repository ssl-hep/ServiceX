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
from servicex_app.models import DatasetFile, TransformationResult, TransformRequest
from servicex_app.transformer_manager import TransformerManager
from tests.resource_test_base import ResourceTestBase


class TestTransformFileComplete(ResourceTestBase):
    def _generate_file_complete_request(self):
        return {
            'file-path': '/foo/bar.root',
            'file-id': 42,
            'status': 'OK',
            'total-time': 100,
            'total-events': 10000,
            'total-bytes': 325683,
            'avg-rate': 30.2
        }

    def test_put_transform_file_complete_files_remaining(self, mocker):
        import servicex_app
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=1)
        TransformRequest.files_remaining = mock_files_remaining

        transform_request_update_mock = \
            mocker.patch.object(TransformRequest, "file_transformed_unsuccessfully")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())
        assert response.status_code == 200
        assert fake_req.finish_time is None
        mock_transform_request_read.assert_called_with('1234')
        transform_request_update_mock.assert_called_with("1234")
        mock_files_remaining.assert_called()
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_unknown_files_remaining(self, mocker):
        import servicex_app
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=None)
        TransformRequest.files_remaining = mock_files_remaining

        transform_request_update_mock = \
            mocker.patch.object(TransformRequest, "file_transformed_unsuccessfully")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())
        assert response.status_code == 200
        assert fake_req.finish_time is None
        mock_transform_request_read.assert_called_with('1234')
        transform_request_update_mock.assert_called_with("1234")
        mock_files_remaining.assert_called()

        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_no_files_remaining(self, mocker):
        import servicex_app
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=0)
        TransformRequest.files_remaining = mock_files_remaining

        transform_request_update_mock = \
            mocker.patch.object(TransformRequest, "file_transformed_unsuccessfully")

        mocker.patch.object(DatasetFile, "get_by_id")
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/BR549/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 200
        assert fake_req.finish_time is not None
        mock_transform_request_read.assert_called_with('BR549')
        transform_request_update_mock.assert_called_with("BR549")
        mock_files_remaining.assert_called()
        mock_transformer_manager.shutdown_transformer_job.assert_called_with('BR549',
                                                                             'my-ws')

    def test_put_transform_file_complete_unknown_request_id(self, mocker):
        import servicex_app
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex_app.models.TransformRequest,
            'lookup',
            return_value=None
        )

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 404
        mock_transform_request_read.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
