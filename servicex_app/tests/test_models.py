from servicex.models import UserModel, TransformRequest


class TestTransformRequest:

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

    def test_files_remaining(self, mocker):
        request = TransformRequest()
        request.files = 17
        TransformRequest.result_count = mocker.PropertyMock(return_value=10)
        assert request.files_remaining == 7

    def test_files_remaining_unknown(self, mocker):
        request = TransformRequest()
        request.files = None
        assert request.files_remaining is None
