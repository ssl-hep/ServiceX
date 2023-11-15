from datetime import datetime, timedelta

from pytest import fixture
from servicex.models import TransformationResult, TransformRequest, UserModel


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
        mock_result_cls.query.filter_by.assert_called_once_with(request_id=request.request_id)
        mock_result_cls.query.filter_by.return_value.all.assert_called_once()

    def test_files_remaining_unknown(self):
        request = TransformRequest()
        request.files = None
        assert request.files_remaining is None
