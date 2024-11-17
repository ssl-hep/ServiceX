# Copyright (c) 2024, IRIS-HEP
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
from datetime import datetime
from unittest.mock import patch
from pytest import fixture

from servicex_app.models import Dataset
from servicex_app_test.resource_test_base import ResourceTestBase


class TestDatasetsGetAll(ResourceTestBase):
    @fixture
    def datasets(self):
        return [
            Dataset(last_used=datetime(2022, 1, 1),
                    last_updated=datetime(2022, 1, 1),
                    id='123',
                    name='dataset1',
                    events=100,
                    size=1000,
                    n_files=1,
                    lookup_status='looking',
                    did_finder='rucio'),
        ]

    @patch('servicex_app.models.Dataset.get_by_did_finder')
    def test_get_all_rucio(self, mock_get_by_did_finder, datasets):
        mock_get_by_did_finder.return_value = datasets
        client = self._test_client()
        response = client.get('/servicex/datasets?did-finder=rucio')
        mock_get_by_did_finder.assert_called_with('rucio', None)
        assert response.status_code == 200

        assert response.json == {
            "datasets": [
                {
                    "last_used": "2022-01-01T00:00:00.000000Z",
                    "last_updated": "2022-01-01T00:00:00.000000Z",
                    "id": "123",
                    'is_stale': None,
                    "did_finder": "rucio",
                    'lookup_status': 'looking',
                    'name': 'dataset1',
                    'size': 1000,
                    'events': 100,
                    'n_files': 1
                }
            ]
        }

    @patch('servicex_app.models.Dataset.get_all')
    def test_get_all(self, mock_get, datasets):
        mock_get.return_value = datasets
        client = self._test_client()
        response = client.get('/servicex/datasets')
        mock_get.assert_called()
        assert response.status_code == 200
