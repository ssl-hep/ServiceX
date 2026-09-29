# Copyright (c) 2019-26, IRIS-HEP
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
import pytest
from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
from rucio.common.exception import DataIdentifierNotFound
from servicex_did_finder_lib.exceptions import (
    LookupFailureException,
    NoSuchDatasetException,
)

from rucio_did_finder.rucio_adapter import RucioAdapter


@pytest.fixture
def did_client(mocker):
    return mocker.MagicMock(DIDClient)


@pytest.fixture
def adapter(mocker, did_client):
    adapter = RucioAdapter(did_client, mocker.MagicMock(ReplicaClient))
    adapter.logger = mocker.MagicMock()
    return adapter


class TestClientLocation:
    def test_location_service_failure_is_logged(self, mocker, monkeypatch, adapter):
        for var in ("SITE_NAME", "RUCIO_LATITUDE", "RUCIO_LONGITUDE"):
            monkeypatch.delenv(var, raising=False)
        error = ConnectionError("unreachable")
        mocker.patch("rucio_did_finder.rucio_adapter.requests.post", side_effect=error)

        assert adapter.client_location() == {}
        adapter.logger.exception.assert_called_once_with(
            error, extra={"error_message": "unreachable"}
        )


class TestListDatasetsForDid:
    def test_container(self, adapter, did_client):
        did_client.get_did.return_value = {"type": "CONTAINER", "length": 2}
        did_client.list_content.return_value = [
            {"scope": "abc", "name": "ds1"},
            {"scope": "abc", "name": "ds2"},
        ]

        assert adapter.list_datasets_for_did("abc:my-container") == [
            ["abc", "ds1"],
            ["abc", "ds2"],
        ]
        did_client.list_content.assert_called_once_with("abc", "my-container")
        adapter.logger.info.assert_called_once_with(
            "abc:my-container is a container of 2 datasets.",
            extra={"dataset_name": "abc:my-container"},
        )

    def test_dataset(self, adapter, did_client):
        did_client.get_did.return_value = {"type": "DATASET", "length": 5}

        assert adapter.list_datasets_for_did("abc:my-ds") == [["abc", "my-ds"]]
        adapter.logger.info.assert_called_once_with(
            "abc:my-ds is a dataset with 5 files.",
            extra={"dataset_name": "abc:my-ds", "num_files": 5},
        )

    def test_file(self, adapter, did_client):
        did_info = {"type": "FILE", "length": None}
        did_client.get_did.return_value = did_info

        did = "abc:my-file"

        assert adapter.list_datasets_for_did(did) == [["abc", "my-file"]]
        adapter.logger.info.assert_called_once_with(
            f"{did} is a file: {did_info}.", extra={"dataset_name": did}
        )

    def test_not_found(self, adapter, did_client):
        did_client.get_did.side_effect = DataIdentifierNotFound

        with pytest.raises(NoSuchDatasetException):
            adapter.list_datasets_for_did("abc:missing")
        adapter.logger.warning.assert_called_once_with(
            "abc:missing not found",
            extra={"dataset_name": "abc:missing", "error_type": "does_not_exist"},
        )

    def test_other_rucio_error(self, adapter, did_client):
        did_client.get_did.side_effect = RuntimeError("boom")

        with pytest.raises(LookupFailureException, match="boom"):
            adapter.list_datasets_for_did("abc:broken")
