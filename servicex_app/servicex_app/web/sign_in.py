from flask import redirect, url_for


def sign_in():
    """Send the user to Globus Auth."""
    return redirect(url_for('auth_callback'))
