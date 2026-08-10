from flask import current_app, redirect, session, url_for


def home():
    """Land signed-in users on their dashboard; send everyone else to sign in."""
    if not current_app.config.get("ENABLE_AUTH"):
        return redirect(url_for("global-dashboard"))
    if session.get("is_authenticated"):
        return redirect(url_for("user-dashboard"))
    return redirect(url_for("sign_in"))
