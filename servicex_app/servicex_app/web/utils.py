from flask import current_app, session
from authlib.integrations.flask_client import OAuth

oauth = None


def user_owns_request(req) -> bool:
    """
    Return True if the signed-in web user is allowed to view this transform
    request, i.e. auth is disabled, they are an admin, or they submitted it.
    """
    if not current_app.config.get("ENABLE_AUTH"):
        return True
    if session.get("admin"):
        return True
    return session.get("user_id") == req.submitted_by


def load_oauth_client():
    global oauth
    if oauth is not None:
        return oauth
    oauth = OAuth()
    oauth.register(
        name="oauth",
        server_metadata_url=current_app.config["OAUTH_METADATA_URL"],
        client_id=current_app.config["OAUTH_CLIENT_ID"],
        client_secret=current_app.config["OAUTH_CLIENT_SECRET"],
        client_kwargs={"scope": "openid profile email"},
    )
    oauth.init_app(current_app)
    return oauth
