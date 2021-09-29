import unittest.mock
from datetime import datetime, timedelta

import sqlalchemy as sqla
from pytest import fixture

from servicex.models import UserModel, TransformRequest, TransformationResult


class TestTransformRequest:
    @fixture
    def mock_result_cls(self, mocker):
        mock_result_cls = mocker.patch("servicex.models.TransformationResult")
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
        mock_dt = mocker.patch("servicex.models.datetime")
        mock_dt.utcnow.return_value = t+delta
        assert request.age == delta
        assert mock_dt.utcnow.called_once()

    def test_incomplete(self):
        for status, expected in [
            ("Submitted", True),
            ("Running", True),
            ("Complete", False),
            ("Fatal", False)
        ]:
            request = TransformRequest()
            request.status = status
            assert request.incomplete == expected

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

    def test_result_count(self, mock_result_cls):
        mock_result_cls.query.filter_by.return_value.count.return_value = 3
        request = TransformRequest(request_id="1234")
        assert request.result_count == 3
        mock_result_cls.query.filter_by.assert_called_once_with(request_id=request.request_id)
        mock_result_cls.query.filter_by.return_value.count.assert_called_once()

    def test_results(self, mock_result_cls):
        results = [TransformationResult(), TransformationResult()]
        mock_result_cls.query.filter_by.return_value.all.return_value = results
        request = TransformRequest(request_id="1234")
        assert request.results == results
        mock_result_cls.query.filter_by.assert_called_once_with(request_id=request.request_id)
        mock_result_cls.query.filter_by.return_value.all.assert_called_once()

    def test_files_remaining(self, mocker):
        request = TransformRequest()
        request.files = 17
        mocker.patch(
            "servicex.models.TransformRequest.result_count",
            new_callable=mocker.PropertyMock,
            return_value=10
        )
        assert request.files_remaining == 7

    def test_files_remaining_unknown(self):
        request = TransformRequest()
        request.files = None
        assert request.files_remaining is None

    def test_files_processed(self, mock_result_cls):
        mock_result_cls.query.filter_by.return_value.count.return_value = 3
        request = TransformRequest(request_id="1234")
        assert request.files_processed == 3
        mock_result_cls.query.filter_by.assert_called_once_with(
            request_id=request.request_id, transform_status="success"
        )
        mock_result_cls.query.filter_by.return_value.count.assert_called_once()

    def test_files_failed(self, mock_result_cls):
        mock_result_cls.query.filter_by.return_value.count.return_value = 3
        request = TransformRequest(request_id="1234")
        assert request.files_failed == 3
        mock_result_cls.query.filter_by.assert_called_once_with(
            request_id=request.request_id, transform_status="failure"
        )
        mock_result_cls.query.filter_by.return_value.count.assert_called_once()

    @unittest.mock.patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_lookup_by_id(self, query_property_getter_mock):
        mock_query = query_property_getter_mock.return_value
        expected = TransformRequest(id=17, request_id="445a9533-edec-4017-a542-86d17d5c166f")
        mock_query.get.return_value = expected
        result = TransformRequest.lookup(expected.id)
        assert result == expected
        mock_query.get.assert_called_once_with(expected.id)
        mock_query.filter_by.assert_not_called()

    @unittest.mock.patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_lookup_by_id_as_str(self, query_property_getter_mock):
        mock_query = query_property_getter_mock.return_value
        expected = TransformRequest(id=17, request_id="445a9533-edec-4017-a542-86d17d5c166f")
        mock_query.get.return_value = expected
        result = TransformRequest.lookup(str(expected.id))
        assert result == expected
        mock_query.get.assert_called_once_with(str(expected.id))
        mock_query.filter_by.assert_not_called()

    @unittest.mock.patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_lookup_by_request_id(self, query_property_getter_mock):
        mock_query = query_property_getter_mock.return_value
        expected = TransformRequest(id=17, request_id="445a9533-edec-4017-a542-86d17d5c166f")
        mock_query.filter_by.return_value.one.return_value = expected
        result = TransformRequest.lookup(expected.request_id)
        assert result == expected
        mock_query.filter_by.assert_called_once_with(request_id=expected.request_id)
        mock_query.filter_by.return_value.one.assert_called_once()
        mock_query.get.assert_not_called()

    @unittest.mock.patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_lookup_not_found(self, query_property_getter_mock):
        mock_query = query_property_getter_mock.return_value
        mock_query.get.side_effect = sqla.orm.exc.NoResultFound
        result = TransformRequest.lookup(12)
        assert result is None
