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
import pytest

from servicex_app.models import DatasetFile, TransformationResult, TransformRequest
from servicex_app.transformer_manager import TransformerManager
from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformFileComplete(ResourceTestBase):

    @pytest.fixture
    def mock_transformer_manager(self, mocker):
        manager = mocker.MagicMock(TransformerManager)
        manager.shutdown_transformer_job = mocker.Mock()
        return manager

    @pytest.fixture
    def fake_transform_request(self):
        return self._generate_transform_request()

    @pytest.fixture
    def mock_transform_request_lookup(self, mocker, fake_transform_request):
        return mocker.patch.object(
            TransformRequest, 'lookup',
            return_value=fake_transform_request,
        )

    @pytest.fixture
    def mock_files_remaining(self, mocker):
        mock = mocker.PropertyMock(return_value=1)
        TransformRequest.files_remaining = mock
        return mock

    @pytest.fixture
    def mock_file_transformed_successfully(self, mocker):
        return mocker.patch.object(
            TransformRequest,
            "file_transformed_successfully")

    @pytest.fixture
    def mock_file_transformed_unsuccessfully(self, mocker):
        return mocker.patch.object(
            TransformRequest,
            "file_transformed_unsuccessfully")

    @pytest.fixture
    def test_client(self, mock_transformer_manager):
        # Assuming _test_client is a method in your test class
        return self._test_client(transformation_manager=mock_transformer_manager)

    @pytest.fixture
    def file_complete_response(self):
        return {
            'file-path': '/foo/bar.root',
            'file-id': 42,
            'status': 'success',
            'total-time': 100,
            'total-events': 10000,
            'total-bytes': 325683,
            'avg-rate': 30.2
        }

    def test_put_transform_file_complete_files_remaining(self,
                                                         mock_transformer_manager,
                                                         mock_files_remaining,
                                                         mock_file_transformed_successfully,
                                                         mock_transform_request_lookup,
                                                         fake_transform_request,
                                                         file_complete_response,
                                                         test_client):
        response = test_client.put('/servicex/internal/transformation/1234/file-complete',
                                   json=file_complete_response)
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None
        mock_transform_request_lookup.assert_called_with('1234')
        mock_file_transformed_successfully.assert_called_with("1234")
        mock_files_remaining.assert_called()
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_unknown_files_remaining(self,
                                                                 mock_transformer_manager,
                                                                 mock_files_remaining,
                                                                 mock_file_transformed_successfully,
                                                                 mock_transform_request_lookup,
                                                                 fake_transform_request,
                                                                 file_complete_response,
                                                                 test_client):
        mock_files_remaining.return_value = None

        response = test_client.put('/servicex/internal/transformation/1234/file-complete',
                                   json=file_complete_response)
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None
        mock_transform_request_lookup.assert_called_with('1234')
        mock_file_transformed_successfully.assert_called_with("1234")
        mock_files_remaining.assert_called()

        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_put_transform_file_complete_no_files_remaining(self, mocker,
                                                            mock_transformer_manager,
                                                            mock_files_remaining,
                                                            mock_file_transformed_successfully,
                                                            mock_transform_request_lookup,
                                                            fake_transform_request,
                                                            file_complete_response,
                                                            test_client):

        mock_files_remaining.return_value = 0

        mocker.patch.object(DatasetFile, "get_by_id")
        mocker.patch.object(TransformationResult, "save_to_db")
        mocker.patch.object(TransformRequest, "save_to_db")

        response = test_client.put('/servicex/internal/transformation/BR549/file-complete',
                                   json=file_complete_response)

        assert response.status_code == 200
        assert fake_transform_request.finish_time is not None
        mock_transform_request_lookup.assert_called_with('BR549')
        mock_file_transformed_successfully.assert_called_with("BR549")
        mock_files_remaining.assert_called()
        mock_transformer_manager.shutdown_transformer_job.assert_called_with('BR549',
                                                                             'my-ws')

    def test_put_transform_file_complete_unknown_request_id(self,
                                                            mock_transformer_manager,
                                                            mock_transform_request_lookup,
                                                            fake_transform_request,
                                                            file_complete_response,
                                                            test_client):
        mock_transform_request_lookup.return_value = None
        response = test_client.put('/servicex/internal/transformation/BR549/file-complete',
                                   json=file_complete_response)

        assert response.status_code == 404
        mock_transform_request_lookup.assert_called_with('BR549')
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
