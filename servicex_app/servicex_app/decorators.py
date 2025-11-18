import os
from functools import wraps
from typing import Callable

from flask import (
    Response,
    current_app,
    make_response,
    redirect,
    request,
    session,
    url_for,
)
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from servicex_app.models import UserModel, db


def jwt_required_if_auth_enabled(*dargs, **dkwargs):
    """
    Wrapper around flask_jwt_extended.jwt_required that is a no-op
    when IS_AUTH_ENABLED != 'True'.
    Supports:
        @jwt_required_if_auth_enabled
        @jwt_required_if_auth_enabled()
        @jwt_required_if_auth_enabled(optional=True)
    """
    auth_enabled = os.environ.get("IS_AUTH_ENABLED", "False") == "True"

    if not auth_enabled:
        # @jwt_required_if_auth_enabled
        if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
            func = dargs[0]

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        # @jwt_required_if_auth_enabled(...)
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        return decorator

    return jwt_required(*dargs, **dkwargs)


@jwt_required_if_auth_enabled
def get_jwt_user():
    user = UserModel.find_by_email(get_jwt_identity())

    return user


def oauth_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """Mark a web route as requiring OAuth sign-in."""

    @wraps(fn)
    def decorated_function(*args, **kwargs) -> Response:
        if not current_app.config.get("ENABLE_AUTH"):
            return fn(*args, **kwargs)

        if not session.get("is_authenticated"):
            return redirect(url_for("sign_in"))

        if not session.get("user_id") and request.path != "/profile/new":
            return redirect(url_for("create_profile"))

        return fn(*args, **kwargs)

    return decorated_function


def auth_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """
    Mark an API resource as requiring JWT authentication.
    Pending or deleted users will receive a 401: Unauthorized response.
    """

    @wraps(fn)
    def inner(*args, **kwargs) -> Response:
        if not current_app.config.get("ENABLE_AUTH"):
            return fn(*args, **kwargs)
        elif session.get("is_authenticated"):
            return fn(*args, **kwargs)
        try:
            verify_jwt_in_request(locations=["headers"])
        except NoAuthorizationError as exc:
            assert "NoAuthorizationError"
            return make_response({"message": str(exc)}, 401)

        # Explicitly start a transaction here to avoid unexpected in_transaction() b
        # in the method wrapped by this decorator.
        with db.session.begin():
            user = get_jwt_user()

            if not user:
                msg = (
                    "Not Authorized: No user found matching this API token. "
                    "Your account may have been deleted. "
                    "Please visit the ServiceX website to obtain a new API token."
                )
                return make_response({"message": msg}, 401)
            elif user.pending:
                msg = (
                    "Not Authorized: Your account is still pending. "
                    "An administrator should approve it shortly. If not, "
                    "please contact the ServiceX admins via email or Slack."
                )
                return make_response({"message": msg}, 401)

        return fn(*args, **kwargs)

    return inner


def admin_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """Mark an API resource as requiring administrator role."""

    @wraps(fn)
    def inner(*args, **kwargs) -> Response:
        msg = "Not Authorized: This resource is restricted to administrators."
        if not current_app.config.get("ENABLE_AUTH"):
            return fn(*args, **kwargs)
        elif session.get("is_authenticated"):
            if session.get("admin"):
                return fn(*args, **kwargs)
            else:
                return make_response({"message": msg}, 401)
        try:
            verify_jwt_in_request(locations=["headers"])
        except NoAuthorizationError as exc:
            assert "NoAuthorizationError"
            return make_response({"message": str(exc)}, 401)

        user = get_jwt_user()
        if not (user and user.admin):
            return make_response({"message": msg}, 401)

        return fn(*args, **kwargs)

    return inner
