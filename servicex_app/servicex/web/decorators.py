from flask import redirect, request, session, url_for, current_app
from functools import wraps


def authenticated(fn):
    """Mark a route as requiring authentication."""

    if not current_app.config.get('ENABLE_AUTH'):
        return fn

    @wraps(fn)
    def decorated_function(*args, **kwargs):
        if not session.get('is_authenticated'):
            return redirect(url_for('sign_in'))

        if not session.get('user_id') and request.path != '/profile/new':
            return redirect(url_for('create_profile'))

        return fn(*args, **kwargs)

    return decorated_function
