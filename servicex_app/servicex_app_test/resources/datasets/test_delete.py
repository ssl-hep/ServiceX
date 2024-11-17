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

from servicex_app.models import Dataset, DatasetFile
from servicex_app_test.resource_test_base import ResourceTestBase


class TestDatasetsDelete(ResourceTestBase):
    @fixture
    def dataset(self):
        dataset = Dataset(last_used=datetime(2022, 1, 1),
                          last_updated=datetime(2022, 1, 1),
                          id='123',
                          stale=False,
                          name='dataset1',
                          events=100,
                          size=1000,
                          n_files=1,
                          lookup_status='looking',
                          did_finder='rucio')
        dataset.files = [
            DatasetFile(
                id=12,
                dataset_id=dataset.id,
                file_size=100,
                file_events=100,
                paths=['root://root.cern.ch/file1.root']
            )
        ]
        return dataset

    @patch('servicex_app.models.Dataset.find_by_id')
    def test_delete_dataset(self, mock_get, dataset, mocker):
        dataset.stale = False
        mock_get.return_value = dataset
        dataset.save_to_db = mocker.Mock()
        client = self._test_client()
        response = client.delete('/servicex/datasets/123')
        mock_get.assert_called()
        assert dataset.stale
        dataset.save_to_db.assert_called()
        assert response.status_code == 200

    @patch('servicex_app.models.Dataset.find_by_id')
    def test_delete_dataset_not_found(self, mock_get):
        mock_get.return_value = None
        client = self._test_client()
        response = client.delete('/servicex/datasets/123')
        mock_get.assert_called()
        assert response.status_code == 404

    @patch('servicex_app.models.Dataset.find_by_id')
    def test_delete_dataset_already_deleted(self, mock_get, dataset):
        dataset.stale = True
        mock_get.return_value = dataset
        client = self._test_client()
        response = client.delete('/servicex/datasets/123')
        mock_get.assert_called()
        assert response.status_code == 400
