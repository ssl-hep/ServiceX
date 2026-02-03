from flask import flash, request, redirect, url_for, session

from servicex_app.models import UserModel
from servicex_app.sso_utils import store_session_tokens
from .utils import load_oauth_client


def auth_callback():
    """Handles the interaction with OIDC Auth."""
    if "error" in request.args:
        error_desc = request.args.get("error_description", request.args["error"])
        flash(
            "You could not be logged into the portal: " + error_desc,
            request.args["error"],
        )
        return redirect("/")
    scheme = "http" if "localhost" in request.base_url else "https"
    redirect_uri = url_for("auth_callback", _external=True, _scheme=scheme)

    oauth = load_oauth_client()

    # If there's no "code" query string param, start a login flow
    if "code" not in request.args:
        return oauth.oauth.authorize_redirect(redirect_uri)

    # Otherwise, we're coming back from OIDC with a code
    tokens = oauth.oauth.authorize_access_token()
    userinfo = tokens["userinfo"]

    # Use SSO utilities to extract user info and store in session
    user_info = store_session_tokens(tokens, userinfo)
    identity_set = user_info["identity_set"]

    for identity in identity_set:
        user = UserModel.find_by_email(identity)
        if user:
            session["user_id"] = user.id
            session["admin"] = user.admin
            session["email"] = identity
            return redirect(url_for("user-dashboard"))
    return redirect(url_for("create_profile"))
