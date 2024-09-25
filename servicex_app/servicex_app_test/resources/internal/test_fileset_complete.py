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
from datetime import timezone, datetime

from servicex_app import LookupResultProcessor, TransformerManager
from servicex_app.dataset_manager import DatasetManager
from servicex_app_test.resource_test_base import ResourceTestBase

from servicex_app.models import DatasetStatus, Dataset, TransformRequest, TransformStatus
from pytest import fixture


class TestFilesetComplete(ResourceTestBase):
    @fixture
    def mock_find_dataset_by_id(self, mocker):
        dm = mocker.Mock()
        dm.dataset = Dataset(name="rucio://my-did?files=1",
                             did_finder="rucio", lookup_status=DatasetStatus.looking,
                             last_used=datetime.now(tz=timezone.utc),
                             last_updated=datetime.fromtimestamp(0))

        dm.name = "rucio://my-did?files=1"
        dm.id = 42

        mock_find_by_id = mocker.patch.object(Dataset, "find_by_id", return_value=dm)
        return mock_find_by_id

    def test_put_fileset_complete(self, mocker, mock_find_dataset_by_id):
        dataset = mock_find_dataset_by_id.return_value

        pending_request = TransformRequest()
        pending_request.status = TransformStatus.pending_lookup
        mock_lookup_pending = mocker.patch.object(TransformRequest,
                                                  "lookup_pending_on_dataset",
                                                  return_value=[pending_request])

        lookup_request = TransformRequest()
        lookup_request.status = TransformStatus.lookup
        mock_lookup_running = mocker.patch.object(TransformRequest,
                                                  "lookup_running_by_dataset_id",
                                                  return_value=[lookup_request])
        mock_processor = mocker.MagicMock(LookupResultProcessor)

        mock_publish_files = mocker.patch.object(DatasetManager, "publish_files")

        client = self._test_client(lookup_result_processor=mock_processor)

        response = client.put('/servicex/internal/transformation/1234/complete',
                              json={
                                  'files': 17,
                                  'total-events': 1024,
                                  'total-bytes': 2046,
                                  'elapsed-time': 42
                              })
        assert response.status_code == 200
        mock_find_dataset_by_id.assert_called_once_with(1234)
        assert dataset.lookup_status == DatasetStatus.complete
        assert dataset.n_files == 17
        assert dataset.events == 1024
        assert dataset.size == 2046

        mock_lookup_pending.assert_called_once_with(1234)
        mock_lookup_running.assert_called_once_with(1234)
        mock_publish_files.assert_called_once_with(pending_request, mock_processor)
        assert pending_request.status == TransformStatus.running
        assert lookup_request.status == TransformStatus.running

    def test_put_fileset_complete_empty_dataset(self, mocker, mock_find_dataset_by_id):
        pending_request = TransformRequest()
        pending_request.status = TransformStatus.pending_lookup

        running_request = TransformRequest()
        running_request.request_id = "111-111"
        running_request.status = TransformStatus.running

        mock_lookup_pending = mocker.patch.object(TransformRequest,
                                                  "lookup_pending_on_dataset",
                                                  return_value=[pending_request])
        mock_lookup_running = mocker.patch.object(TransformRequest,
                                                  "lookup_running_by_dataset_id",
                                                  return_value=[running_request])

        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()

        client = self._test_client(lookup_result_processor=mock_processor,
                                   transformation_manager=mock_transformer_manager)

        response = client.put('/servicex/internal/transformation/12345/complete',
                              json={
                                  'files': 0,
                                  'total-events': 0,
                                  'total-bytes': 0,
                                  'elapsed-time': 0
                              })

        assert response.status_code == 200
        mock_find_dataset_by_id.assert_called_once_with(12345)
        mock_lookup_pending.assert_called_once_with(12345)
        mock_lookup_running.assert_called_once_with(12345)
        mock_transformer_manager.shutdown_transformer_job.assert_called_with("111-111", 'my-ws')
        assert running_request.status == TransformStatus.complete
        assert pending_request.status == TransformStatus.complete
