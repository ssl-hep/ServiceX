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

from servicex.did_finder.lookup_request import LookupRequest
from servicex.did_finder.rucio_adapter import RucioAdapter


class TestLookupRequest:
    def test_init(self, mocker):
        mock_rucio = mocker.MagicMock(RucioAdapter)
        request = LookupRequest("my-did", mock_rucio)
        assert request.rucio_adapter == mock_rucio
        assert request.did == 'my-did'

        def test_lookup_files(self, mocker):
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

            request = LookupRequest("my-did", mock_rucio)

            assert len(request.lookup_files()) == 10

            mock_rucio.list_files_for_did.assert_called_with("my-did")

    @pytest.mark.asyncio
    async def test_lookup_files_empty_did(self, mocker):
        'Make sure that a DID with zero files correctly returns zero files'
        mock_rucio = mocker.MagicMock(RucioAdapter)
        mock_rucio.list_files_for_did.return_value = []

        request = LookupRequest("my-did", mock_rucio)

        assert len(await request.lookup_files()) == 0
