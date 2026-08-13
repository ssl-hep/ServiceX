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

import psycopg2
import pytest

from servicex_app.models import (
    Dataset,
    DatasetFile,
    TransformationResult,
    TransformRequest,
    TransformStatus,
)
from servicex_app.resources.internal.transformer_file_complete import (
    TransformerFileComplete,
)
from servicex_app.transformer_manager import TransformerManager
from servicex_app_test.resource_test_base import ResourceTestBase


class TestTransformFileComplete(ResourceTestBase):
    module = "servicex_app.resources.internal.transformer_file_complete"

    @pytest.fixture
    def mock_transformer_manager(self, mocker):
        manager = mocker.MagicMock(TransformerManager)
        manager.shutdown_transformer_job = mocker.Mock()
        return manager

    @pytest.fixture
    def db_session(self, mocker):
        db = mocker.patch(f"{self.module}.db")
        db.session = mocker.Mock()
        db.session.begin = mocker.MagicMock()
        return db.session

    @pytest.fixture
    def fake_transform_request(self):
        fake_request = self._generate_transform_request()
        fake_request.request_id = "1234"
        fake_request.status = TransformStatus.running
        fake_request.files = 10
        return fake_request

    @pytest.fixture
    def trqmock(self, mocker, fake_transform_request):
        rv = mocker.Mock()
        rv.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (  # noqa: E501
            fake_transform_request
        )
        return rv

    @pytest.fixture
    def othermock(self, mocker):
        rv = mocker.Mock()
        rv.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (  # noqa: E501
            None
        )
        return rv

    @pytest.fixture
    def dsfilemock(self, mocker):
        rv = mocker.Mock()
        rv.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (  # noqa: E501
            None
        )
        return rv

    @pytest.fixture
    def mock_transform_request_lookup(self, db_session, trqmock, othermock, dsfilemock):
        def switcher(cls):
            if cls == TransformRequest:
                return trqmock
            elif cls == DatasetFile:
                return dsfilemock
            else:
                return othermock

        db_session.query.side_effect = switcher
        return trqmock.filter_by.return_value.with_for_update.return_value.one_or_none

    @pytest.fixture
    def test_client(self, mock_transformer_manager):
        # Assuming _test_client is a method in your test class
        return self._test_client(transformation_manager=mock_transformer_manager)

    @pytest.fixture
    def file_complete_response(self):
        return {
            "file-path": "/foo/bar.root",
            "file-id": 42,
            "status": "success",
            "total-time": 100,
            "total-events": 10000,
            "total-bytes": 325683,
            "avg-rate": 30.2,
            "s3-object-name": "file://s3-object-name",
        }

    @pytest.fixture
    def fake_transformation_result(self):
        return TransformationResult(
            file_path="/foo/bar.root",
            file_id=42,
            transform_status="success",
            transform_time=100,
            total_events=10000,
            total_bytes=325684,
            avg_rate=30.2,
            s3_object_name="file://s3-object-name",
        )

    def test_put_transform_file_complete_files_remaining(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 0
        fake_transform_request.files_failed = 2
        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None
        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 1
        assert fake_transform_request.files_failed == 2
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
        db_session.add.assert_called_once()
        assert db_session.add.call_args[0][0].file_id == 42

    def test_put_transform_file_complete_failed_files_remaining(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 0
        fake_transform_request.files_failed = 2
        file_complete_response["status"] = "failed"
        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None
        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 0
        assert fake_transform_request.files_failed == 3
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
        db_session.add.assert_called_once()
        assert db_session.add.call_args[0][0].file_id == 42

    def test_put_transform_file_complete_first_file_files_remaining(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 0
        fake_transform_request.files_failed = 0
        fake_transform_request.total_bytes = None
        fake_transform_request.total_events = None
        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 1
        assert fake_transform_request.files_failed == 0
        assert (
            fake_transform_request.total_bytes == file_complete_response["total-bytes"]
        )
        assert (
            fake_transform_request.total_events
            == file_complete_response["total-events"]
        )
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
        db_session.add.assert_called_once()
        assert db_session.add.call_args[0][0].file_id == 42

    def test_put_transform_file_complete_unknown_files_remaining(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files = None
        fake_transform_request.files_completed = 0
        fake_transform_request.files_failed = 2

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None
        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 1
        assert fake_transform_request.files_failed == 2
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()
        db_session.add.assert_called_once()
        assert db_session.add.call_args[0][0].file_id == 42

    def test_put_transform_file_complete_no_files_remaining(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 7
        fake_transform_request.files_failed = 2

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert response.status_code == 200
        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 8
        assert fake_transform_request.files_failed == 2

        assert db_session.add.call_count == 2
        assert isinstance(db_session.add.mock_calls[0][1][0], TransformationResult)
        assert db_session.add.mock_calls[0][1][0].file_id == 42

        updated_transform = db_session.add.mock_calls[1][1][0]
        assert isinstance(updated_transform, TransformRequest)
        assert updated_transform.status == TransformStatus.complete
        assert updated_transform.finish_time is not None
        mock_transformer_manager.shutdown_transformer_job.assert_called_with(
            "1234", "my-ws"
        )

    def test_put_transform_file_complete_duplicate_report(
        self,
        mocker,
        mock_transformer_manager,
        db_session,
        trqmock,
        othermock,
        mock_transform_request_lookup,
        fake_transform_request,
        fake_transformation_result,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 6
        fake_transform_request.files_failed = 2

        orig_total_bytes = fake_transform_request.total_bytes
        response1 = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert fake_transform_request.total_bytes == (
            orig_total_bytes + file_complete_response["total-bytes"]
        )

        fake_transformation_result.total_bytes = file_complete_response["total-bytes"]

        othermock.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
            fake_transformation_result
        )

        file_complete_response["total-bytes"] += 1000

        response2 = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 7
        assert fake_transform_request.files_failed == 2

        assert fake_transform_request.total_bytes == (
            orig_total_bytes + file_complete_response["total-bytes"]
        )

        assert db_session.add.call_count == 2
        assert isinstance(db_session.add.mock_calls[0][1][0], TransformationResult)
        assert db_session.add.mock_calls[0][1][0].file_id == 42

        assert db_session.add.mock_calls[1][1][0].file_id == 42

    def test_put_transform_file_complete_duplicate_report_previous_failure(
        self,
        mocker,
        mock_transformer_manager,
        db_session,
        trqmock,
        othermock,
        mock_transform_request_lookup,
        fake_transform_request,
        fake_transformation_result,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 6
        fake_transform_request.files_failed = 2

        fake_transformation_result.transform_status = "failure"
        othermock.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
            fake_transformation_result
        )

        response1 = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert response1.status_code == 200

        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 7
        assert fake_transform_request.files_failed == 1

        assert db_session.add.call_count == 1
        assert isinstance(db_session.add.mock_calls[0][1][0], TransformationResult)
        assert db_session.add.mock_calls[0][1][0].file_id == 42

    def test_put_transform_file_complete_duplicate_report_weird_transform_state(
        self,
        mocker,
        mock_transformer_manager,
        db_session,
        trqmock,
        othermock,
        mock_transform_request_lookup,
        fake_transform_request,
        fake_transformation_result,
        file_complete_response,
        test_client,
    ):
        fake_transform_request.files_completed = 6
        fake_transform_request.files_failed = 2
        fake_transform_request.total_events = None

        othermock.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
            fake_transformation_result
        )

        response1 = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert response1.status_code == 200

        trqmock.filter_by.assert_called_with(request_id="1234")
        assert fake_transform_request.files_completed == 6
        assert fake_transform_request.files_failed == 2
        assert (
            fake_transform_request.total_bytes == file_complete_response["total-bytes"]
        )

        assert db_session.add.call_count == 1
        assert isinstance(db_session.add.mock_calls[0][1][0], TransformationResult)
        assert db_session.add.mock_calls[0][1][0].file_id == 42

    def test_put_transform_file_complete_unknown_request_id(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        trqmock.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (
            None
        )
        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )

        assert response.status_code == 404
        trqmock.filter_by.assert_called_with(request_id="1234")
        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_database_error_request_read(
        self,
        mocker,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):
        trqmock.filter_by.return_value.with_for_update.return_value.one_or_none.side_effect = [
            psycopg2.OperationalError("server closed the connection unexpectedly"),
            fake_transform_request,
        ]

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None

        # Verify that we retried after the database error
        assert mock_transform_request_lookup.call_count == 2
        trqmock.filter_by.assert_called_with(request_id="1234")

        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_database_error_request_update(
        self,
        mock_transformer_manager,
        db_session,
        trqmock,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):

        db_session.flush.side_effect = [
            psycopg2.OperationalError("server closed the connection unexpectedly"),
            fake_transform_request,
        ]

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        assert fake_transform_request.finish_time is None

        # Verify that we retried after the database error
        trqmock.filter_by.assert_called_with(request_id="1234")

        mock_transformer_manager.shutdown_transformer_job.assert_not_called()

    def test_database_error_transform_result_save(
        self,
        mock_transformer_manager,
        db_session,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):

        db_session.add.side_effect = [
            psycopg2.OperationalError("server closed the connection unexpectedly"),
            fake_transform_request,
        ]

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200

    def test_database_error_transform_complete(
        self,
        mock_transformer_manager,
        db_session,
        mock_transform_request_lookup,
        fake_transform_request,
        file_complete_response,
        test_client,
    ):

        # Trigger the fileset complete by setting the files_remaining to 0
        fake_transform_request.files_completed = 9

        db_session.add.side_effect = [
            fake_transform_request,
            psycopg2.OperationalError("server closed the connection unexpectedly"),
            fake_transform_request,
        ]

        response = test_client.put(
            "/servicex/internal/transformation/1234/file-complete",
            json=file_complete_response,
        )
        assert response.status_code == 200
        # add called once for the transform result and then once for the updated transform request
        # once with a failure and once successfully
        assert db_session.add.call_count == 3


class TestBackfillDatasetStats:
    """Direct unit tests for TransformerFileComplete.backfill_dataset_stats."""

    @staticmethod
    def _session(mocker, file_row=None, dataset_row=None):
        session = mocker.Mock()
        session.begin = mocker.MagicMock()

        def switcher(cls):
            chain = mocker.Mock()
            if cls is DatasetFile:
                chain.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (  # noqa: E501
                    file_row
                )
            elif cls is Dataset:
                chain.filter_by.return_value.with_for_update.return_value.one_or_none.return_value = (  # noqa: E501
                    dataset_row
                )
            return chain

        session.query.side_effect = switcher
        return session

    @staticmethod
    def _info(**overrides):
        base = {
            "file-id": 42,
            "status": "success",
            "total-events": 12345,
            "total-bytes": 6789,
        }
        base.update(overrides)
        return base

    def test_skips_when_status_not_success(self, mocker):
        session = self._session(mocker)
        TransformerFileComplete.backfill_dataset_stats(
            session, self._info(status="failure")
        )
        session.query.assert_not_called()

    def test_skips_when_events_and_size_both_zero(self, mocker):
        session = self._session(mocker)
        TransformerFileComplete.backfill_dataset_stats(
            session, self._info(**{"total-events": 0, "total-bytes": 0})
        )
        session.query.assert_not_called()

    def test_skips_when_file_row_missing(self, mocker):
        session = self._session(mocker, file_row=None)
        TransformerFileComplete.backfill_dataset_stats(session, self._info())
        # DatasetFile queried, but never reaches Dataset
        assert Dataset not in [call.args[0] for call in session.query.mock_calls]

    def test_skips_when_file_row_already_populated(self, mocker):
        file_row = mocker.Mock()
        file_row.file_events = 999
        file_row.file_size = 999
        file_row.dataset_id = 7
        session = self._session(mocker, file_row=file_row)

        TransformerFileComplete.backfill_dataset_stats(session, self._info())

        # File row values not overwritten
        assert file_row.file_events == 999
        assert file_row.file_size == 999
        # Dataset should NOT be queried since deltas are both zero
        queried_classes = [call.args[0] for call in session.query.mock_calls if call.args]
        assert Dataset not in queried_classes

    def test_backfills_file_row_and_dataset(self, mocker):
        file_row = mocker.Mock()
        file_row.file_events = 0
        file_row.file_size = 0
        file_row.dataset_id = 7
        dataset_row = mocker.Mock()
        dataset_row.events = 100
        dataset_row.size = 500
        session = self._session(mocker, file_row=file_row, dataset_row=dataset_row)

        TransformerFileComplete.backfill_dataset_stats(session, self._info())

        assert file_row.file_events == 12345
        assert file_row.file_size == 6789
        assert dataset_row.events == 100 + 12345
        assert dataset_row.size == 500 + 6789

    def test_backfills_from_none_dataset_counters(self, mocker):
        file_row = mocker.Mock()
        file_row.file_events = 0
        file_row.file_size = 0
        file_row.dataset_id = 7
        dataset_row = mocker.Mock()
        dataset_row.events = None
        dataset_row.size = None
        session = self._session(mocker, file_row=file_row, dataset_row=dataset_row)

        TransformerFileComplete.backfill_dataset_stats(session, self._info())

        assert dataset_row.events == 12345
        assert dataset_row.size == 6789

    def test_backfills_only_events_when_size_already_set(self, mocker):
        file_row = mocker.Mock()
        file_row.file_events = 0
        file_row.file_size = 999
        file_row.dataset_id = 7
        dataset_row = mocker.Mock()
        dataset_row.events = 0
        dataset_row.size = 0
        session = self._session(mocker, file_row=file_row, dataset_row=dataset_row)

        TransformerFileComplete.backfill_dataset_stats(session, self._info())

        assert file_row.file_events == 12345
        assert file_row.file_size == 999
        assert dataset_row.events == 12345
        assert dataset_row.size == 0

    def test_skips_when_dataset_row_missing(self, mocker):
        file_row = mocker.Mock()
        file_row.file_events = 0
        file_row.file_size = 0
        file_row.dataset_id = 7
        session = self._session(mocker, file_row=file_row, dataset_row=None)

        TransformerFileComplete.backfill_dataset_stats(session, self._info())

        # File row is still updated even though Dataset lookup returned None
        assert file_row.file_events == 12345
        assert file_row.file_size == 6789
