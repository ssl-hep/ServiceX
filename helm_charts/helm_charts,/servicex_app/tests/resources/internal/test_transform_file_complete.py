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
from servicex.models import TransformRequest, DatasetFile, TransformationResult
from tests.resource_test_base import ResourceTestBase


class TestTransformFileComplete(ResourceTestBase):
    def _generate_file_complete_request(self):
        return {
            'file-path': '/foo/bar.root',
            'file-id': 42,
            'status': 'OK',
            'total-time': 100,
            'num-messages': 1024,
            'total-events': 10000,
            'total-bytes': 325683,
            'avg-rate': 30.2
        }

    def test_put_transform_file_complete_files_remaining(self, mocker):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=1)
        TransformRequest.files_remaining = mock_files_remaining

        mocker.patch.object(DatasetFile, "get_by_id")
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())
        assert response.status_code == 200
        assert fake_req.finish_time is None
        mock_transform_request_read.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_unknown_files_remaining(self, mocker):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=None)
        TransformRequest.files_remaining = mock_files_remaining

        mocker.patch.object(DatasetFile, "get_by_id")
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())
        assert response.status_code == 200
        assert fake_req.finish_time is None
        mock_transform_request_read.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_no_files_remaining(self, mocker):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        fake_req = self._generate_transform_request()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest, 'lookup', return_value=fake_req
        )

        mock_files_remaining = mocker.PropertyMock(return_value=0)
        TransformRequest.files_remaining = mock_files_remaining

        mocker.patch.object(DatasetFile, "get_by_id")
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 200
        assert fake_req.finish_time is not None
        mock_transform_request_read.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_called_with('1234',
                                                                             'my-ws')

    def test_put_transform_file_complete_unknown_request_id(self, mocker):
        import servicex
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mock_transform_request_read = mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=None
        )

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 404
        mock_transform_request_read.assert_called_with('1234')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def _generate_dataset_file(self):
        mock_dataset_file = DatasetFile()
        mock_dataset_file.adler32 = '123-455'
        mock_dataset_file.file_size = 0
        mock_dataset_file.file_events = 0
        mock_dataset_file.paths = ["/foo/bar1.root", "/foo/bar2.root"],
        mock_dataset_file.request_id = 'BR549'
        return mock_dataset_file

    def test_file_transform_complete_files_remain(self, mocker):
        import servicex

        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        mock_files_remaining = mocker.PropertyMock(return_value=1)
        TransformRequest.files_remaining = mock_files_remaining

        mocker.patch.object(DatasetFile, "get_by_id",
                            return_value=self._generate_dataset_file())
        mocker.patch.object(TransformationResult, "save_to_db")

        client = self._test_client(transformation_manager=mock_transformer_manager)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 200

    def test_file_transform_complete_no_files_remain(self, mocker,
                                                     mock_rabbit_adaptor):
        import servicex

        mocker.patch.object(DatasetFile, "get_by_id",
                            return_value=self._generate_dataset_file())
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        mock_transformer_manager = mocker.MagicMock(TransformerManager)

        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()
        mocker.patch.object(
            servicex.models.TransformRequest,
            'lookup',
            return_value=self._generate_transform_request())

        mock_files_remaining = mocker.PropertyMock(return_value=0)
        TransformRequest.files_remaining = mock_files_remaining

        client = self._test_client(transformation_manager=mock_transformer_manager,
                                   rabbit_adaptor=mock_rabbit_adaptor)
        response = client.put('/servicex/internal/transformation/1234/file-complete',
                              json=self._generate_file_complete_request())

        assert response.status_code == 200
