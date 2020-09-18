from functools import wraps
from typing import Callable

from flask import redirect, request, session, url_for, current_app, \
    make_response, Response
from flask_jwt_extended import get_jwt_identity, jwt_required

from servicex.models import UserModel


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

    if not current_app.config.get('ENABLE_AUTH'):
        return fn

    @wraps(fn)
    def decorated_function(*args, **kwargs) -> Response:
        user = UserModel.find_by_sub(get_jwt_identity())
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

    return jwt_required(decorated_function)


def admin_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """Mark an API resource as requiring administrator role."""

    if not current_app.config.get('ENABLE_AUTH'):
        return fn

    @wraps(fn)
    def decorated_function(*args, **kwargs) -> Response:
        user = UserModel.find_by_sub(get_jwt_identity())
        msg = 'Not Authorized: This resource is restricted to administrators.'
        if not (user and user.admin):
            return make_response({'message': msg}, 401)
        return fn(*args, **kwargs)

    return jwt_required(decorated_function)
