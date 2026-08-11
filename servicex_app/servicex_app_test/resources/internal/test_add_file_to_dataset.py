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
from unittest.mock import ANY, call

from pytest import fixture
from servicex_app import LookupResultProcessor
from servicex_app_test.resource_test_base import ResourceTestBase

from servicex_app.dataset_manager import DatasetManager

from servicex_app.models import TransformRequest
from servicex_app.transformer_manager import TransformerManager


class TestAddFileToDataset(ResourceTestBase):
    @fixture
    def mock_transformer_manager(self, mocker):
        return mocker.MagicMock(TransformerManager)

    @fixture
    def mock_transformer_lookup(self, mocker):
        first_request = self._generate_transform_request()
        first_request.request_id = "first_request"
        first_request.staus = "Running"
        first_request.files = 0

        second_request = self._generate_transform_request()
        second_request.request_id = "second_request"
        second_request.status = "Submitted"
        second_request.files = 0

        mock_transformer_lookup = mocker.patch.object(
            TransformRequest,
            "lookup_running_by_dataset_id",
            return_value=[first_request, second_request],
        )
        return mock_transformer_lookup

    @fixture
    def mock_dataset_manager_from_id(self, mocker):
        mock_dataset_manager = mocker.MagicMock(DatasetManager)
        mock_dataset_manager.name = "mock_dataset"
        mock_dataset_manager.id = 42
        mock_dataset_manager.dataset = mocker.Mock()
        mock_dataset_manager.dataset.id = 42

        mock_dataset_manager_find = mocker.patch.object(
            DatasetManager, "from_dataset_id", return_value=mock_dataset_manager
        )
        return mock_dataset_manager_find

    def test_put_new_file(
        self,
        mocker,
        mock_dataset_manager_from_id,
        mock_transformer_lookup,
        mock_transformer_manager,
    ):
        mock_add_files = mock_dataset_manager_from_id.return_value.add_files

        def fake_add_files(files, requests, _processor):
            for req in requests:
                req.files += len(files)

        mock_add_files.side_effect = fake_add_files

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(
            lookup_result_processor=mock_processor,
            transformation_manager=mock_transformer_manager,
        )
        with client.application.app_context():

            response = client.put(
                "/servicex/internal/transformation/1234/files",
                json={
                    "paths": ["/foo/bar1.root", "/foo/bar2.root"],
                    "adler32": "12345",
                    "file_size": 1024,
                    "file_events": 500,
                },
            )
            assert response.status_code == 200
            assert response.json == {"dataset_id": "1234"}

            mock_dataset_manager_from_id.assert_called_with("1234", ANY, ANY)
            mock_add_files.assert_called()
            dataset_file_list = mock_add_files.call_args[0][0]
            running_transform_list = mock_add_files.call_args[0][1]
            assert len(dataset_file_list) == 1
            assert dataset_file_list[0].paths == "/foo/bar1.root,/foo/bar2.root"
            assert len(running_transform_list) == 2
            mock_transformer_manager.patch_transformer_parallelism.assert_has_calls(
                [
                    call("first_request", "my-ws", 1),
                    call("second_request", "my-ws", 1),
                ]
            )
            assert (
                mock_transformer_manager.patch_transformer_parallelism.call_count
                == 2
            )

    def test_put_new_file_bulk(
        self,
        mocker,
        mock_transformer_lookup,
        mock_dataset_manager_from_id,
        mock_transformer_manager,
    ):
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_add_files = mock_dataset_manager_from_id.return_value.add_files

        def fake_add_files(files, requests, _processor):
            for req in requests:
                req.files += len(files)

        mock_add_files.side_effect = fake_add_files

        client = self._test_client(
            lookup_result_processor=mock_processor,
            transformation_manager=mock_transformer_manager,
        )

        response = client.put(
            "/servicex/internal/transformation/1234/files",
            json=[
                {
                    "paths": ["/foo/bar1.root", "/foo/bar2.root"],
                    "adler32": "12345",
                    "file_size": 1024,
                    "file_events": 500,
                },
                {
                    "paths": ["/foo1/bar1.root", "/foo1/bar2.root"],
                    "adler32": "12345",
                    "file_size": 2048,
                    "file_events": 500,
                },
            ],
        )
        assert response.status_code == 200
        mock_dataset_manager_from_id.assert_called_with("1234", ANY, ANY)
        mock_add_files.assert_called()
        dataset_file_list = mock_add_files.call_args[0][0]
        running_transform_list = mock_add_files.call_args[0][1]
        assert len(dataset_file_list) == 2
        assert dataset_file_list[0].paths == "/foo/bar1.root,/foo/bar2.root"
        assert dataset_file_list[1].paths == "/foo1/bar1.root,/foo1/bar2.root"
        assert len(running_transform_list) == 2
        assert running_transform_list[0].request_id == "first_request"
        assert running_transform_list[1].request_id == "second_request"
        assert response.json == {"dataset_id": "1234"}

        mock_transformer_manager.patch_transformer_parallelism.assert_has_calls(
            [
                call("first_request", "my-ws", 2),
                call("second_request", "my-ws", 2),
            ]
        )
        assert (
            mock_transformer_manager.patch_transformer_parallelism.call_count
            == 2
        )

    def test_put_new_file_with_exception(
        self,
        mocker,
        mock_dataset_manager_from_id,
        mock_transformer_lookup,
        mock_transformer_manager,
    ):
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_processor.add_files_to_processing_queue.side_effect = Exception("Test")

        client = self._test_client(
            lookup_result_processor=mock_processor,
            transformation_manager=mock_transformer_manager,
        )

        response = client.put(
            "/servicex/internal/transformation/1234/files",
            json={
                "paths": [123, 123],
                "adler32": "12345",
                "file_size": 1024,
                "file_events": 500,
            },
        )
        assert response.status_code == 500
        assert response.json == {
            "message": "Something went wrong: sequence item 0: expected str instance, int found"
        }
        mock_transformer_manager.patch_transformer_parallelism.assert_not_called()
