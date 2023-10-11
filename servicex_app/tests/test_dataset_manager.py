# Copyright (c) 2022, IRIS-HEP
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
from pytest import fixture
from servicex.dataset_manager import DatasetManager
from servicex.did_parser import DIDParser
from servicex.models import Dataset, DatasetFile, TransformRequest
from tests.resource_test_base import ResourceTestBase

from servicex.lookup_result_processor import LookupResultProcessor


def mock_dataset(status: str, mocker) -> Dataset:
    ds = mocker.MagicMock()
    ds.lookup_status = status
    ds.id = "da-tas-et-id"
    return ds


class TestDatasetManager(ResourceTestBase):

    @fixture
    def mock_dataset_cls(self, mocker):

        mock_dataset.save_to_db = mocker.Mock()
        mock_dataset_cls = mocker.patch("servicex.dataset_manager.Dataset", return_value=mock_dataset("created", mocker))
        mock_query = mocker.Mock(return_value=None)
        mock_dataset_cls.query.find_by_name = mock_query
        mock_dataset_cls.find_by_name.return_value = None
        return mock_dataset_cls

    @fixture
    def mock_dataset_file_cls(self, mocker):
        mock_dataset_file = DatasetFile(
            dataset_id="da-tas-et-id",
            paths="paths",
            adler32="adler32",
            file_size="file_size",
            file_events="file_events"
        )
        mock_dataset_file.save_to_db = mocker.Mock()
        mock_dataset_cls = mocker.patch("servicex.dataset_manager.DatasetFile", return_value=mock_dataset_file)
        return mock_dataset_cls

    def test_invalid_constructor(self, mock_dataset_cls, mock_dataset_file_cls):
        with pytest.raises(ValueError):
            DatasetManager()

        with pytest.raises(ValueError):
            DatasetManager(did="did", file_list=["file1", "file2"])

        DatasetManager(did=DIDParser("did"))
        DatasetManager(file_list=["file1", "file2"])

    def test_dataset_from_did(self, mock_dataset_cls):
        d = DatasetManager(did=DIDParser("rucio://my-did?files=1"))
        mock_dataset_cls.assert_called()
        assert mock_dataset_cls.call_args.kwargs['name'] == "rucio://my-did?files=1"
        assert mock_dataset_cls.call_args.kwargs['did_finder'] == "rucio"
        assert mock_dataset_cls.call_args.kwargs['lookup_status'] == "created"

        assert d.name == "rucio://my-did?files=1"

    def test_dataset_from_filelist(self, mock_dataset_cls, mock_dataset_file_cls):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        file_list_hash = "985d119e9da637c5b7f89c133f60689259f0fe5db0ee4b3d993270aafdc5b82a"
        d = DatasetManager(file_list=file_list)
        assert (d.name == file_list_hash)

        mock_dataset_cls.assert_called()
        assert mock_dataset_cls.call_args.kwargs['name'] == file_list_hash
        assert mock_dataset_cls.call_args.kwargs['did_finder'] == "user"
        assert mock_dataset_cls.call_args.kwargs['lookup_status'] == "created"

        mock_dataset_file_cls.assert_called()
        call0 = mock_dataset_file_cls.call_args_list[0]
        assert call0.kwargs['paths'] == file_list[0]
        assert call0.kwargs['dataset_id'] == "da-tas-et-id"
        call1 = mock_dataset_file_cls.call_args_list[1]
        assert call1.kwargs['paths'] == file_list[1]

    def test_existing_dataset(self, mocker, mock_dataset_cls):
        ds = mock_dataset("complete", mocker)
        mock_dataset_cls.find_by_name.return_value = ds
        d = DatasetManager(did=DIDParser("rucio://my-did?files=1"))
        mock_dataset_cls.assert_not_called()
        assert d.dataset is not None
        assert d.name == "rucio://my-did?files=1"


    def test_lookup_not_required_filelist(self, mock_dataset_cls, mock_dataset_file_cls):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        d = DatasetManager(file_list=file_list)
        d.dataset.lookupstatus = 'created'
        assert not d.is_lookup_required

    def test_lookup_required_did(self, mock_dataset_cls, mock_dataset_file_cls):
        d1 = DatasetManager(did=DIDParser("rucio://my-did?files=1"))
        assert d1.is_lookup_required

        d1.dataset.lookup_status = "complete"
        assert not d1.is_lookup_required

    def test_is_complete(self, mock_dataset_cls, mock_dataset_file_cls, mocker):
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        d = DatasetManager(file_list=file_list)
        d.dataset = mock_dataset("created", mocker)
        assert not d.is_complete

        d.dataset = mock_dataset("complete", mocker)
        assert d.is_complete

    def test_submit_lookup_request(self, mocker, mock_dataset_cls, mock_dataset_file_cls):
        mock_rabbit = mocker.Mock()
        d = DatasetManager(did=DIDParser("rucio://my-did?files=1"))
        d.submit_lookup_request("http://hit-me/here", mock_rabbit)

        mock_rabbit.basic_publish.assert_called_with(exchange="",
                                                     routing_key='rucio_did_requests',
                                                     body='{"dataset_id": "da-tas-et-id", '
                                                          '"did": "my-did?files=1", '
                                                           '"endpoint": "http://hit-me/here"}')

    def test_publish_files(self, mocker, mock_dataset_cls, mock_dataset_file_cls):
        mock_processor = mocker.MagicMock(spec=LookupResultProcessor)
        file_list = ["root://eospublic.cern.ch/1.root", "root://eospublic.cern.ch/2.root"]
        transform_request = TransformRequest()
        transform_request.request_id = "462-33"
        transform_request.selection = "test-string"

        d = DatasetManager(file_list=file_list)
        d.dataset.n_files=2
        d.publish_files(request=transform_request, lookup_result_processor=mock_processor)
        assert transform_request.files == 2
        mock_processor.add_files_to_processing_queue.assert_called_with(transform_request, files=file_list)