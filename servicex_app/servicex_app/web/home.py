from flask import current_app, redirect, render_template, session, url_for


def home():
    """Land signed-in users on their dashboard; welcome page for everyone else."""
    if not current_app.config.get("ENABLE_AUTH"):
        return redirect(url_for("global-dashboard"))
    if session.get("is_authenticated"):
        return redirect(url_for("user-dashboard"))
    return render_template("home.html")
