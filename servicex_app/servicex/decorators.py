from functools import wraps

from flask import redirect, request, session, url_for, current_app, make_response
from flask_jwt_extended import get_jwt_identity, jwt_required

from servicex.models import UserModel


def authenticated(fn):
    """Mark a route as requiring authentication."""

    @wraps(fn)
    def decorated_function(*args, **kwargs):
        if not current_app.config.get('ENABLE_AUTH'):
            return fn(*args, **kwargs)

        if not session.get('is_authenticated'):
            return redirect(url_for('sign_in'))

        if not session.get('user_id') and request.path != '/profile/new':
            return redirect(url_for('create_profile'))

        return fn(*args, **kwargs)

    return decorated_function


def admin_required(fn):
    """Mark an API resource as requiring administrator role."""

    msg = 'Not Authorized: This resource is restricted to administrators.'

    @wraps(fn)
    def decorated_function(*args, **kwargs):
        if not current_app.config.get('ENABLE_AUTH'):
            return fn(*args, **kwargs)

        user = UserModel.find_by_sub(get_jwt_identity())
        if not (user and user.admin):
            return make_response({'message': msg}, 401)
        return jwt_required(fn(*args, **kwargs))

    return decorated_function
