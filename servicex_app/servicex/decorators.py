from functools import wraps
from typing import Callable

from flask import (Response, make_response, redirect, request,
                   session, url_for)
from flask_jwt_extended import (get_jwt_identity, jwt_required,
                                verify_jwt_in_request)
from flask_jwt_extended.exceptions import NoAuthorizationError
from jwt import ExpiredSignatureError

from servicex.models import UserModel
from flask import current_app

from servicex.web.utils import refresh_cern_public_key


@jwt_required()
def get_jwt_user():
    jwt_val = get_jwt_identity()
    user = UserModel.find_by_sub(jwt_val)
    return user


def oauth_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """Mark a web route as requiring OAuth sign-in."""

    @wraps(fn)
    def decorated_function(*args, **kwargs) -> Response:
        if not current_app.config.get('ENABLE_AUTH'):
            return fn(*args, **kwargs)

        if not session.get('is_authenticated'):
            return redirect(url_for('sign_in'))

        if not session.get('user_id') and request.path != '/profile/new':
            return redirect(url_for('create_profile'))

        return fn(*args, **kwargs)

    return decorated_function


def auth_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """
    Mark an API resource as requiring JWT authentication.
    Pending or deleted users will receive a 401: Unauthorized response.
    """

    @wraps(fn)
    def inner(*args, **kwargs) -> Response:
        if not current_app.config.get('ENABLE_AUTH'):
            return fn(*args, **kwargs)
        elif session.get('is_authenticated'):
            return fn(*args, **kwargs)
        elif current_app.config.get("JWT_ISSUER") == "globus":
            try:
                verify_jwt_in_request(locations=["headers"])
            except NoAuthorizationError as exc:
                assert "NoAuthorizationError"
                return make_response({'message': str(exc)}, 401)
            user = get_jwt_user()
            if not user:
                msg = 'Not Authorized: No user found matching this API token. ' \
                    'Your account may have been deleted. ' \
                    'Please visit the ServiceX website to obtain a new API token.'
                return make_response({'message': msg}, 401)
            elif user.pending:
                msg = 'Not Authorized: Your account is still pending. ' \
                    'An administrator should approve it shortly. If not, ' \
                    'please contact the ServiceX admins via email or Slack.'
                return make_response({'message': msg}, 401)

            return fn(*args, **kwargs)
        else:
            refresh_cern_public_key()

            try:
                verify_jwt_in_request(locations=["headers"])
            except NoAuthorizationError as exc:
                assert "NoAuthorizationError"
                return make_response({'message': str(exc)}, 401)
            except ExpiredSignatureError as exc:
                return make_response({'message': str(exc)}, 401)
            return fn(*args, **kwargs)
    return inner


def admin_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """Mark an API resource as requiring administrator role."""

    @wraps(fn)
    def inner(*args, **kwargs) -> Response:
        msg = 'Not Authorized: This resource is restricted to administrators.'
        if not current_app.config.get('ENABLE_AUTH'):
            return fn(*args, **kwargs)
        elif session.get('is_authenticated'):
            if session.get('admin'):
                return fn(*args, **kwargs)
            else:
                return make_response({'message': msg}, 401)
        try:
            verify_jwt_in_request(locations=["headers"])
        except NoAuthorizationError as exc:
            assert "NoAuthorizationError"
            return make_response({'message': str(exc)}, 401)

        user = get_jwt_user()
        if not (user and user.admin):
            return make_response({'message': msg}, 401)

        return fn(*args, **kwargs)

    return inner
