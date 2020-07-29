from flask import redirect, request, session, url_for
from functools import wraps


def authenticated(fn):
    """Mark a route as requiring authentication."""

    @wraps(fn)
    def decorated_function(*args, **kwargs):
        if not session.get('is_authenticated'):
            return redirect(url_for('sign_in', next=request.url))

        if request.path == url_for('sign_out'):
            return fn(*args, **kwargs)

        if (not (session.get('name') and session.get('email'))) \
                and request.path != '/profile':
            return redirect(url_for('create_profile', next=request.url))

        if not session.get('user_id') and request.path != '/profile/new':
            return redirect(url_for('create_profile', next=request.url))

        return fn(*args, **kwargs)

    return decorated_function
