from pytest import fixture


@fixture
def mock_jwt_extended(mocker):
    """
    During unit tests, functions from Flask-JWT-extended are mocked to do nothing.
    """
    mocker.patch("servicex_app.decorators.verify_jwt_in_request")
    mocker.patch("servicex_app.decorators.get_jwt_identity", return_value="testuser")


@fixture(scope="session")
def celery_config():
    return {
        "broker_url": "memory://localhost/",
    }
