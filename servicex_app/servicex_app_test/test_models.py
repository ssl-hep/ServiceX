import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import text

import pytest
from pytest import fixture, MonkeyPatch

import servicex_app
from servicex_app.models import TransformationResult, TransformRequest, UserModel


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

    def test_total_cache_size(self, app_context, mocker, monkeypatch: MonkeyPatch):
        monkeypatch.setenv(
            "ALLOWED_DOCKER_REGISTRIES",
            '{"docker.io": {"allowedImagePrefixes": ["sslhep/servicex_science_image_topcp:"]}}',
        )
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
