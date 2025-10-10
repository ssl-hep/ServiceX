# Copyright (c) 2019-25, IRIS-HEP
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

from rucio_did_finder.lookup_request import LookupRequest
from rucio_did_finder.rucio_adapter import RucioAdapter

from servicex_did_finder_lib.exceptions import (
    BadDatasetNameException,
    LookupFailureException,
)

from rucio.client.didclient import DIDClient
from rucio.client.replicaclient import ReplicaClient
from rucio.common.exception import DataIdentifierNotFound


class TestLookupRequest:
    def test_init(self, mocker):
        mock_rucio = mocker.MagicMock(RucioAdapter)
        request = LookupRequest("my-did", mock_rucio)
        assert request.rucio_adapter == mock_rucio
        assert request.did == "my-did"

    def test_lookup_files(self, mocker):
        mock_rucio = mocker.MagicMock(RucioAdapter)
        rucio_file_list1 = [
            {
                "paths": ["root://file1" + str(i)],
                "file_size": 31400,
                "file_events": 5000,
                "adler32": 21231,
            }
            for i in range(10)
        ]
        rucio_file_list2 = [
            {
                "paths": ["root://file2" + str(i)],
                "file_size": 31400,
                "file_events": 5000,
                "adler32": 21231,
            }
            for i in range(10)
        ]

        mock_rucio.list_files_for_did.return_value = iter([rucio_file_list1, rucio_file_list2])

        request = LookupRequest("my-did", mock_rucio)

        assert len(sum([_ for _ in request.lookup_files()], [])) == 20

        mock_rucio.list_files_for_did.assert_called_with("my-did")

    def test_lookup_files_no_replica(self, mocker):
        mock_did_client = mocker.MagicMock(DIDClient)
        mock_replica_client = mocker.MagicMock(ReplicaClient)

        mocker.patch("rucio_did_finder.rucio_adapter.RucioAdapter.list_datasets_for_did", return_value=["abc:def"])
        mock_replica_client.list_replicas.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
 <file name="ghi">
 <identity>abc:ghi</identity>
 <hash type="adler32">430cf1b4</hash>
 <size>19969184</size>
 <glfn name="/atlas/rucio/ghi"></glfn>
 </file>
</metalink>"""

        request = LookupRequest("my-did", RucioAdapter(mock_did_client, mock_replica_client))

        with pytest.raises(LookupFailureException):
            [_ for _ in request.lookup_files()]

    def test_lookup_files_no_dataset(self, mocker):
        mock_scope_client = mocker.patch('rucio_did_finder.rucio_adapter.ScopeClient')
        mock_scope_client.list_scopes.return_value = ["abc"]
        mock_did_client = mocker.MagicMock(DIDClient)
        mock_did_client.get_did.side_effect = DataIdentifierNotFound
        mock_replica_client = mocker.MagicMock(ReplicaClient)

        request = LookupRequest("my-did", RucioAdapter(mock_did_client, mock_replica_client))

        with pytest.raises(BadDatasetNameException):
            [_ for _ in request.lookup_files()]

    def test_rucio_scope_problem(self, mocker):
        mock_scope_client = mocker.patch('rucio_did_finder.rucio_adapter.ScopeClient')
        mock_scope_client.list_scopes.return_value = ["abc"]
        mock_did_client = mocker.MagicMock(DIDClient)
        mock_replica_client = mocker.MagicMock(ReplicaClient)
        request = LookupRequest("my-did", RucioAdapter(mock_did_client, mock_replica_client))
        with pytest.raises(BadDatasetNameException):
            [_ for _ in request.lookup_files()]

    def test_rucio_no_dataset(self, mocker):
        mock_scope_client = mocker.patch('rucio_did_finder.rucio_adapter.ScopeClient')
        mock_scope_client.list_scopes.return_value = ["abc"]
        mock_did_client = mocker.MagicMock(DIDClient)
        mock_replica_client = mocker.MagicMock(ReplicaClient)
        request = LookupRequest("my-did", RucioAdapter(mock_did_client, mock_replica_client))
        with pytest.raises(BadDatasetNameException):
            [_ for _ in request.lookup_files()]
