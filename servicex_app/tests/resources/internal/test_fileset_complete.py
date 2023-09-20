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
from servicex import LookupResultProcessor
from tests.resource_test_base import ResourceTestBase


class TestFilesetComplete(ResourceTestBase):

    def test_put_fileset_complete(self, mocker):
        import servicex

        mocker.patch.object(servicex.models.Dataset, 'find_by_id',
                            return_value=self._generate_dataset())

        mock_dataset_complete_to_db = mocker.patch.object(
            servicex.models.db.session,
            'commit',
            return_value=None
        )

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/1234/complete',
                              json={
                                  'files': 17,
                                  'total-events': 1024,
                                  'total-bytes': 2046,
                                  'elapsed-time': 42
                              })
        assert response.status_code == 200
        mock_dataset_complete_to_db.assert_called_once()

    def test_put_fileset_complete_empty_dataset(self, mocker):
        import servicex

        mocker.patch.object(servicex.models.Dataset, 'find_by_id',
                            return_value=self._generate_dataset())

        mock_dataset_complete_to_db = mocker.patch.object(
            servicex.models.db.session,
            'commit',
            return_value=None
        )

        mock_processor = mocker.MagicMock(LookupResultProcessor)

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/BR549/complete',
                              json={
                                  'files': 0,
                                  'total-events': 0,
                                  'total-bytes': 0,
                                  'elapsed-time': 0
                              })

        assert response.status_code == 200
        mock_dataset_complete_to_db.assert_called_once()
