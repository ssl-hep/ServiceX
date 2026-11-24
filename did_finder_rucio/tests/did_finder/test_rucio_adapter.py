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

from servicex_did_finder_lib.accumulator import Accumulator
from servicex_did_finder_lib.did_summary import DIDSummary
from servicex_did_finder_lib.servicex_adaptor import ServiceXAdapter

from rucio_did_finder.rucio_adapter import RucioAdapter


@pytest.fixture
def did_client(mocker):
    return mocker.MagicMock(DIDClient)


@pytest.fixture
def adapter(mocker, did_client):
    # The real extract_scope needs a rucio.cfg, which isn't available in tests
    mocker.patch(
        "rucio_did_finder.rucio_adapter.extract_scope",
        side_effect=lambda did: did.split(":", 1),
    )
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


TWO_FILE_METALINK = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
 <file name="f0">
 <identity>user.x:f0</identity>
 <hash type="adler32">430cf1b4</hash>
 <size>100</size>
 <url location="A" priority="1">root://a/f0</url>
 <url location="B" priority="2">root://b/f0</url>
 </file>
 <file name="f1">
 <identity>user.x:f1</identity>
 <hash type="adler32">0000aaaa</hash>
 <size>200</size>
 <url location="A" priority="1">root://a/f1</url>
 </file>
</metalink>"""


class TestListFilesForDid:
    @pytest.fixture
    def replica_adapter(self, adapter, mocker):
        mocker.patch.object(
            adapter, "list_datasets_for_did", return_value=[["user.x", "ds"]]
        )
        mocker.patch.object(adapter, "client_location", return_value={})
        adapter.did_client.list_files.return_value = [{"name": "f0"}, {"name": "f1"}]
        adapter.replica_client.list_replicas.return_value = TWO_FILE_METALINK
        return adapter

    def test_file_key_is_scope_and_name(self, replica_adapter):
        (files,) = list(replica_adapter.list_files_for_did("user.x:ds", "cloud=CERN"))

        assert files == [
            {
                "adler32": "430cf1b4",
                "file_size": 100,
                "file_events": 0,
                "paths": ["root://a/f0", "root://b/f0"],
                "file_key": "user.x:f0",
            },
            {
                "adler32": "0000aaaa",
                "file_size": 200,
                "file_events": 0,
                "paths": ["root://a/f1"],
                "file_key": "user.x:f1",
            },
        ]

    def test_file_key_keeps_scope_for_logical_files(self, replica_adapter):
        replica_adapter.report_logical_files = True

        (files,) = list(replica_adapter.list_files_for_did("user.x:ds", "cloud=CERN"))

        assert [f["paths"] for f in files] == [["f0"], ["f1"]]
        assert [f["file_key"] for f in files] == ["user.x:f0", "user.x:f1"]


class TestCeleryPathIgnoresFileKey:
    def test_accumulator_drops_file_key_from_put(self, mocker):
        """The Celery DIDFinderApp PUTs files through Accumulator and
        put_file_add_bulk; an extra file_key must not break it or reach the app."""
        put = mocker.patch("servicex_did_finder_lib.servicex_adaptor.requests.put")
        sx = ServiceXAdapter(
            endpoint="http://sx/servicex/internal/transformation/", dataset_id=7
        )
        summary = DIDSummary("user.x:ds")
        acc = Accumulator(sx, summary)
        acc.add(
            [
                {
                    "adler32": "1",
                    "file_size": 100,
                    "file_events": 0,
                    "paths": ["root://a/f0"],
                    "file_key": "user.x:f0",
                },
                {
                    "adler32": "2",
                    "file_size": 200,
                    "file_events": 0,
                    "paths": ["root://a/f1"],
                    "file_key": "user.x:f1",
                },
            ]
        )

        acc.send_on(-1)

        (call,) = put.call_args_list
        assert call.args == ("http://sx/servicex/internal/transformation/7/files",)
        body = call.kwargs["json"]
        assert [f["paths"] for f in body] == [["root://a/f0"], ["root://a/f1"]]
        assert all("file_key" not in f for f in body)
        assert summary.file_count == 2
        assert summary.total_bytes == 300
