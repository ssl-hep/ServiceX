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
from asyncio import Queue
from unittest.mock import call
import pytest

import servicex
from servicex.did_finder.lookup_request import LookupRequest
from servicex.did_finder.rucio_adapter import RucioAdapter
from servicex.did_finder.servicex_adapter import ServiceXAdapter


class TestLookupRequest:
    def test_init(self, mocker):
        mock_rucio = mocker.MagicMock(RucioAdapter)
        mock_servicex = mocker.MagicMock(ServiceXAdapter)
        request = LookupRequest("my-did", mock_rucio, mock_servicex)
        assert request.rucio_adapter == mock_rucio
        assert request.did == 'my-did'
        assert request.chunk_size == 1000

    @pytest.mark.asyncio
    async def test_lookup_files(self, mocker):
        'Good lookup, chunk size is same as file size'
        mock_rucio = mocker.MagicMock(RucioAdapter)
        rucio_file_list = [
            {
                "scope": "my-scope",
                "name": "file"+str(i),
                "bytes": 31400,
                "events": 5000
            } for i in range(10)
        ]

        mock_rucio.list_files_for_did.return_value = rucio_file_list

        mock_rucio.find_replicas.return_value = [
            {
                'adler32': 21231,
                'bytes': 1122233344,
            }
        ]

        request = LookupRequest(
            "my-did",
            mock_rucio,
            threads=5,
            chunk_size=1)

        output_files = []
        async for f in request.lookup_files():
            output_files.append(f)
        assert len(output_files) == 10

        mock_rucio.list_files_for_did.assert_called_with("my-did")

    @pytest.mark.asyncio
    async def test_lookup_files_chunked(self, mocker):
        'Good lookup, make sure chunking is set correctly'
        mock_rucio = mocker.MagicMock(RucioAdapter)
        rucio_file_list = [
            {
                "scope": "my-scope",
                "name": "file"+str(i),
                "bytes": 31400,
                "events": 5000
            } for i in range(10)
        ]

        mock_rucio.list_files_for_did.return_value = rucio_file_list
        # Chunk size is 2, so return 2 files with each find_replicas call
        mock_rucio.find_replicas.return_value = [
            {
                'adler32': 21231,
                'bytes': 1122233344,
            },
            {
                'adler32': 212312,
                'bytes': 11222333442,
            }

        ]

        request = LookupRequest(
            "my-did",
            mock_rucio,
            threads=5,
            chunk_size=2)

        output_files = []
        async for f in request.lookup_files():
            output_files.append(f)
        assert len(output_files) == 10

        mock_rucio.list_files_for_did.assert_called_with("my-did")

    @pytest.mark.asyncio
    async def test_lookup_files_empty_did(self, mocker):
        'Make sure that a DID with zero files correctly returns zero files from its iterator'
        mock_rucio = mocker.MagicMock(RucioAdapter)
        mock_rucio.list_files_for_did.return_value = iter([])

        mocker.patch("threading.Thread")
        request = LookupRequest(
            "my-did",
            mock_rucio,
            threads=5,
            chunk_size=2)

        output_files = []
        async for f in request.lookup_files():
            output_files.append(f)
        assert len(output_files) == 0

    @pytest.mark.asyncio
    async def test_lookup_files_did_not_found(self, mocker):
        'Make sure exception is thrown if DID is not found'
        mock_rucio = mocker.MagicMock(RucioAdapter)
        mock_rucio.list_files_for_did.return_value = None

        request = LookupRequest(
            "my-did",
            mock_rucio,
            threads=5,
            chunk_size=2)

        with pytest.raises(Exception) as e:
            async for _ in request.lookup_files():
                pass

        assert "DID not found" in str(e)

    def test_replica_lookup(self, mocker):
        mock_rucio = mocker.MagicMock(RucioAdapter)
        mock_rucio.find_replicas.return_value = [
            {
                "adler32": "ad:efb2b057",
                "events": 1000,
                "bytes": 689123
             }
        ]

        input_data = [
            {
                'name': 'file1',
                'scope': 'fork'
            },
            {
                'name': 'file2',
                'scope': 'fork'
            }
        ]

        mock_sel_path = mocker.patch.object(
            servicex.did_finder.rucio_adapter.RucioAdapter, "get_sel_path")
        mock_sel_path.return_value = "mc15_13TeV:DAOD_STDM3.05630052._000013.pool.root.1"

        request = LookupRequest("my-did", mock_rucio, chunk_size=2)
        request.replica_lookup(input_data)
        mock_rucio.find_replicas.assert_called_with([{'name': "file1", 'scope': "fork"}, {'name': "file2", 'scope': 'fork'}], None)
        mock_sel_path.assert_called_with(
            mock_rucio.find_replicas.return_value[0],
            '',
            None
        )

        # mock_servicex.put_file_add.assert_called_with({
        #     'adler32': 'ad:efb2b057',
        #     'file_events': 0,
        #     'file_path': 'mc15_13TeV:DAOD_STDM3.05630052._000013.pool.root.1',
        #     'file_size': 689123,
        #     'req_id': '123-45'
        # })

        # mock_servicex.post_preflight_check.assert_called_once()
        # mock_servicex.post_preflight_check.assert_called_with({
        #     'adler32': 'ad:efb2b057',
        #     'file_events': 0,
        #     'file_path': 'mc15_13TeV:DAOD_STDM3.05630052._000013.pool.root.1',
        #     'file_size': 689123,
        #     'req_id': '123-45'
        # })

    # def test_fileset_complete(self, mocker):
    #     mock_rucio = mocker.MagicMock(RucioAdapter)
    #     mock_rucio.find_replicas.return_value = [
    #         {
    #             "adler32": "ad:efb2b057",
    #             "events": 1000,
    #             "bytes": 689123
    #          },
    #         {
    #             "adler32": "ad:efb2b058",
    #             "events": 2000,
    #             "bytes": 689124
    #         }
    #     ]

    #     mock_sel_path = mocker.patch.object(
    #         servicex.did_finder.rucio_adapter.RucioAdapter, "get_sel_path")
    #     mock_sel_path.side_effect = [
    #         "mc15_13TeV:DAOD_STDM3.05630052._000013.pool.root.1",
    #         "mc15_13TeV:DAOD_STDM3.05630052._000013.pool.root.2"
    #     ]

    #     mock_servicex = mocker.MagicMock(ServiceXAdapter)
    #     request = LookupRequest("123-45", "my-did", mock_rucio, mock_servicex, chunk_size=2)
    #     request.sample_submitted = True
    #     request.file_list = ["file1", "file2"]

    #     request.replica_lookup_queue = Queue(5)
    #     request.replica_lookup_queue.put_nowait(["file1", "file2"])
    #     request.replica_lookup()

    #     mock_servicex.put_fileset_complete.assert_called_once()
    #     fileset_complete_args = mock_servicex.put_fileset_complete.call_args[0][0]
    #     assert fileset_complete_args['files'] == 2
    #     assert fileset_complete_args['total-bytes'] == 689123 + 689124
