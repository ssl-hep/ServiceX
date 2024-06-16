from pytest import fixture


@fixture
def mock_jwt_extended(mocker):
    """
    During unit tests, functions from Flask-JWT-extended are mocked to do nothing.
    """
    mocker.patch('servicex_app.decorators.verify_jwt_in_request')
