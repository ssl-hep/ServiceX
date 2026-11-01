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
from servicex_app_test.resource_test_base import ResourceTestBase

from servicex_app.models import (
    DatasetStatus,
    Dataset,
    TransformRequest,
    TransformStatus,
)
from pytest import fixture, mark


class TestFilesetError(ResourceTestBase):
    @fixture
    def mock_find_dataset_by_id(self, mocker):
        dm = mocker.Mock()
        dm.dataset = Dataset(
            name="rucio://my-did?files=1",
            did_finder="rucio",
            lookup_status=DatasetStatus.looking,
            last_used=datetime.now(tz=timezone.utc),
            last_updated=datetime.fromtimestamp(0),
        )

        dm.name = "rucio://my-did?files=1"
        dm.id = 42

        mock_find_by_id = mocker.patch.object(Dataset, "find_by_id", return_value=dm)
        return mock_find_by_id

    @mark.parametrize("error", ["does_not_exist", "bad_name", "internal_failure"])
    def test_put_fileset_error(self, mocker, mock_find_dataset_by_id, error):
        dataset = mock_find_dataset_by_id.return_value

        pending_request = TransformRequest()
        pending_request.request_id = "222-222"
        pending_request.status = TransformStatus.pending_lookup

        lookup_request = TransformRequest()
        lookup_request.request_id = "111-111"
        lookup_request.status = TransformStatus.lookup
        mock_lock_awaiting = mocker.patch.object(
            TransformRequest,
            "lock_awaiting_dataset",
            return_value=[lookup_request, pending_request],
        )
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()

        client = self._test_client(
            lookup_result_processor=mock_processor,
            transformation_manager=mock_transformer_manager,
        )

        response = client.put(
            "/servicex/internal/transformation/1234/error",
            json={"elapsed-time": 0, "error-type": error, "message": "honk"},
        )
        assert response.status_code == 200
        mock_find_dataset_by_id.assert_called_once_with(1234)
        assert dataset.lookup_status == DatasetStatus(error)
        assert dataset.stale

        mock_lock_awaiting.assert_called_once_with(1234)
        assert pending_request.status == TransformStatus.bad_dataset
        assert lookup_request.status == TransformStatus.bad_dataset
        assert pending_request.finish_time is not None
        assert lookup_request.finish_time is not None
        assert mock_transformer_manager.shutdown_transformer_job.call_count == 2
        mock_transformer_manager.shutdown_transformer_job.assert_any_call(
            "111-111", "my-ws"
        )
        mock_transformer_manager.shutdown_transformer_job.assert_any_call(
            "222-222", "my-ws"
        )

    def test_put_fileset_error_shutdown_failure(self, mocker, mock_find_dataset_by_id):
        lookup_request = TransformRequest()
        lookup_request.request_id = "111-111"
        lookup_request.status = TransformStatus.lookup
        mocker.patch.object(
            TransformRequest, "lock_awaiting_dataset", return_value=[lookup_request]
        )
        mock_db = mocker.patch("servicex_app.resources.internal.fileset_error.db")
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock(
            side_effect=ConnectionError("kubernetes api unreachable")
        )

        client = self._test_client(
            lookup_result_processor=mocker.MagicMock(LookupResultProcessor),
            transformation_manager=mock_transformer_manager,
        )

        response = client.put(
            "/servicex/internal/transformation/1234/error",
            json={"elapsed-time": 0, "error-type": "bad_name", "message": "honk"},
        )
        # The status is committed before the shutdown, which only logs its failure
        assert response.status_code == 200
        assert lookup_request.status == TransformStatus.bad_dataset
        assert mock_db.session.commit.call_count == 2
        mock_transformer_manager.shutdown_transformer_job.assert_called_once_with(
            "111-111", "my-ws"
        )

    def test_put_fileset_error_invalid_did(self, mocker):
        pending_request = TransformRequest()
        pending_request.request_id = "222-222"
        pending_request.status = TransformStatus.pending_lookup

        lookup_request = TransformRequest()
        lookup_request.request_id = "111-111"
        lookup_request.status = TransformStatus.lookup
        mock_lock_awaiting = mocker.patch.object(
            TransformRequest,
            "lock_awaiting_dataset",
            return_value=[lookup_request, pending_request],
        )

        mock_find_dataset_by_id = mocker.patch.object(
            Dataset, "find_by_id", return_value=None
        )
        mock_processor = mocker.MagicMock(LookupResultProcessor)
        mock_transformer_manager = mocker.MagicMock(TransformerManager)
        mock_transformer_manager.shutdown_transformer_job = mocker.Mock()

        client = self._test_client(
            lookup_result_processor=mock_processor,
            transformation_manager=mock_transformer_manager,
        )

        response = client.put(
            "/servicex/internal/transformation/1234/error",
            json={"elapsed-time": 0, "error-type": "bad_dataset", "message": "honk"},
        )
        assert response.status_code == 422
        mock_find_dataset_by_id.assert_called_once_with(1234)

        mock_lock_awaiting.assert_not_called()
