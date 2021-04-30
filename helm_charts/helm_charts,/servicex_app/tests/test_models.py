from servicex.models import TransformRequest


class TestTransformRequest:

    def test_files_remaining(self, mocker):
        request = TransformRequest()
        request.files = 17
        TransformRequest.result_count = mocker.PropertyMock(return_value=10)
        assert request.files_remaining == 7

    def test_files_remaining_unknown(self, mocker):
        request = TransformRequest()
        request.files = None
        assert request.files_remaining is None
