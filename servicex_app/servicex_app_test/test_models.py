import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import text

import pytest
from pytest import fixture

import servicex_app
from servicex_app.models import (
    Dataset,
    LogMessage,
    TransformationResult,
    TransformRequest,
    UserModel,
)


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    # Get the directory where the current file is located
    current_dir = Path(__file__).parent

    os.environ["APP_CONFIG_FILE"] = str(current_dir / "test.config")
    app = servicex_app.create_app()
    app.config["TESTING"] = True
    # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app


@pytest.fixture
def app_context(app):
    """Create an application context."""
    with app.app_context():
        yield app


class TestTransformRequest:
    @fixture
    def mock_result_cls(self, mocker):
        mock_result_cls = mocker.patch("servicex_app.models.TransformationResult")
        mock_query = mocker.MagicMock()
        mock_result_cls.query.filter_by.return_value = mock_query
        return mock_result_cls

    @fixture
    def mock_query(self, mocker):
        return TransformRequest.query

    def test_age(self, mocker):
        request = TransformRequest()
        t = datetime(2021, 1, 1)
        delta = timedelta(days=1, hours=3, minutes=5)
        request.submit_time = t
        mock_dt = mocker.patch("servicex_app.models.datetime")
        mock_dt.utcnow.return_value = t + delta
        assert request.age == delta
        mock_dt.utcnow.assert_called_once()

    def test_submitter_name(self):
        user = UserModel()
        user.id = 1234
        user.name = "Leonardo"
        request = TransformRequest()
        request.submitted_by = user.id
        request.user = user
        assert request.submitter_name == user.name

    def test_submitted_name_deleted(self):
        user = UserModel()
        user.id = 1234
        user.name = "Leonardo"
        request = TransformRequest()
        request.submitted_by = user.id
        request.user = None
        assert request.submitter_name == "[deleted]"

    def test_submitted_name_none(self):
        request = TransformRequest()
        assert request.submitter_name is None

    def test_results(self, mock_result_cls):
        results = [TransformationResult(), TransformationResult()]
        mock_result_cls.query.filter_by.return_value.all.return_value = results
        request = TransformRequest(request_id="1234")
        assert request.results == results
        mock_result_cls.query.filter_by.assert_called_once_with(
            request_id=request.request_id
        )
        mock_result_cls.query.filter_by.return_value.all.assert_called_once()

    def test_files_remaining_unknown(self):
        request = TransformRequest()
        request.files = None
        assert request.files_remaining is None

    def test_total_cache_size(self, mocker):
        with patch("servicex_app.models.db") as mock_db:
            q = mocker.MagicMock()
            q.scalar.return_value = 1000
            mock_db.session.query.return_value = q
            size1 = TransformRequest().total_cache_size()
            assert size1 == 1000

            q.scalar.return_value = None
            size2 = TransformRequest().total_cache_size()
            assert size2 == 0

    def test_threshold_reached_returns_correct_submit_time(self, app_context):
        """Test that the method returns the correct submit_time when threshold is reached."""
        with patch("servicex_app.models.db") as mock_db:

            # Arrange
            expected_time = datetime(2025, 1, 15, 10, 30, 0)
            mock_row = (
                1,
                expected_time,
                1500,
            )  # request_id, submit_time, cumulative_bytes

            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row

            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result
            mock_db.engine.connect.return_value.__enter__.return_value = mock_conn

            threshold = 1000

            # Act
            result = servicex_app.models.TransformRequest.latest_request_to_accumulated_cache_size(
                threshold
            )
            # Assert
            assert result == expected_time
            mock_conn.execute.assert_called_once()

            # Verify the SQL query was called with correct parameters
            call_args = mock_conn.execute.call_args
            assert isinstance(call_args[0][0], type(text("")))
            assert call_args[0][1] == {"threshold": threshold}

    def test_threshold_reached_handles_none(self, app_context):
        """Test that the method returns none when there are no records that
        satisfy the threshold.
        """
        with patch("servicex_app.models.db") as mock_db:
            # Arrange
            mock_result = MagicMock()
            mock_result.fetchone.return_value = None

            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result
            mock_db.engine.connect.return_value.__enter__.return_value = mock_conn

            threshold = 1000

            # Act
            result = servicex_app.models.TransformRequest.latest_request_to_accumulated_cache_size(
                threshold
            )

            # Assert
            assert result is None
            mock_conn.execute.assert_called_once()


class TestTransformRequestPurge:
    """
    purge() is the whole teardown for a transform, shared by the delete endpoint
    and the expiry sweep. It must never commit: both callers wrap it in their own
    transaction so the results, the log records and the request go together.
    """

    @fixture
    def transform(self):
        request = TransformRequest()
        request.request_id = "BR549"
        return request

    def test_purge(self, transform, mocker):
        session = mocker.MagicMock()
        object_store = mocker.MagicMock()
        mocker.patch.object(LogMessage, "delete_by_request_id", return_value=7)

        assert transform.purge(session, object_store) == 7

        session.query.assert_called_once_with(TransformationResult)
        session.query.return_value.filter_by.assert_called_once_with(request_id="BR549")
        LogMessage.delete_by_request_id.assert_called_once_with(
            "BR549", session=session
        )
        object_store.delete_bucket_and_contents.assert_called_once_with("BR549")
        session.delete.assert_called_once_with(transform)
        assert not session.commit.called

    def test_purge_without_object_store(self, transform, mocker):
        """Object store is optional; the rest of the teardown still runs."""
        session = mocker.MagicMock()
        mocker.patch.object(LogMessage, "delete_by_request_id", return_value=0)

        assert transform.purge(session) == 0
        session.delete.assert_called_once_with(transform)


class TestLogMessage:
    def test_delete_by_request_id(self, mocker):
        with patch("servicex_app.models.db") as mock_db:
            query = mocker.MagicMock()
            query.filter_by.return_value.delete.return_value = 3
            mock_db.session.query.return_value = query

            assert LogMessage.delete_by_request_id("1234") == 3

            mock_db.session.query.assert_called_once_with(LogMessage)
            query.filter_by.assert_called_once_with(request_id="1234")
            query.filter_by.return_value.delete.assert_called_once_with(
                synchronize_session=False
            )

    def test_delete_by_request_id_explicit_session(self, mocker):
        """An injected session is used in preference to db.session, which is
        what the lifecycle ops rely on."""
        with patch("servicex_app.models.db") as mock_db:
            session = mocker.MagicMock()
            session.query.return_value.filter_by.return_value.delete.return_value = 1

            assert LogMessage.delete_by_request_id("1234", session=session) == 1

            session.query.assert_called_once_with(LogMessage)
            assert not mock_db.session.query.called

    def test_delete_by_request_id_without_id(self, mocker):
        """Filtering on a null request_id would match every DID finder record,
        so an empty id must delete nothing."""
        with patch("servicex_app.models.db") as mock_db:
            session = mocker.MagicMock()

            assert LogMessage.delete_by_request_id(None, session=session) == 0
            assert LogMessage.delete_by_request_id("") == 0

            assert not session.query.called
            assert not mock_db.session.query.called

    def test_delete_by_dataset_id(self, mocker):
        with patch("servicex_app.models.db") as mock_db:
            query = mocker.MagicMock()
            query.filter_by.return_value.delete.return_value = 2
            mock_db.session.query.return_value = query

            assert LogMessage.delete_by_dataset_id(42) == 2

            mock_db.session.query.assert_called_once_with(LogMessage)
            query.filter_by.assert_called_once_with(dataset_id=42)
            query.filter_by.return_value.delete.assert_called_once_with(
                synchronize_session=False
            )

    def test_delete_by_dataset_id_without_id(self, mocker):
        """Filtering on a null dataset_id would match every transform record."""
        with patch("servicex_app.models.db") as mock_db:
            session = mocker.MagicMock()

            assert LogMessage.delete_by_dataset_id(None, session=session) == 0

            assert not session.query.called
            assert not mock_db.session.query.called


class TestDatasetDelete:
    @fixture
    def dataset(self, mocker):
        dataset = Dataset(id=42, name="dataset1", stale=False)
        dataset.save_to_db = mocker.Mock()
        return dataset

    def test_delete_dataset_purges_logs(self, dataset, mocker):
        mock_purge = mocker.patch("servicex_app.models.LogMessage.delete_by_dataset_id")
        mocker.patch("servicex_app.models.Dataset.find_by_id", return_value=dataset)

        # The purge has to land before the commit so that both share a
        # transaction, so watch the order the two are called in
        calls = mocker.Mock()
        calls.attach_mock(mock_purge, "purge_logs")
        calls.attach_mock(dataset.save_to_db, "save_to_db")

        assert Dataset.delete_dataset(42) is True
        assert dataset.stale
        mock_purge.assert_called_once_with(42)
        assert [_[0] for _ in calls.mock_calls] == ["purge_logs", "save_to_db"]

    def test_delete_dataset_not_found(self, mocker):
        mock_purge = mocker.patch("servicex_app.models.LogMessage.delete_by_dataset_id")
        mocker.patch("servicex_app.models.Dataset.find_by_id", return_value=None)

        assert Dataset.delete_dataset(42) is None
        assert not mock_purge.called

    def test_delete_dataset_already_stale(self, dataset, mocker):
        dataset.stale = True
        mock_purge = mocker.patch("servicex_app.models.LogMessage.delete_by_dataset_id")
        mocker.patch("servicex_app.models.Dataset.find_by_id", return_value=dataset)

        assert Dataset.delete_dataset(42) is False
        assert not mock_purge.called
        assert not dataset.save_to_db.called
