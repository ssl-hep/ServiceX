from flask import flash, request, redirect, url_for, session

from servicex_app.models import UserModel
from .utils import load_oauth_client


def auth_callback():
    """Handles the interaction with OIDC Auth."""
    if "error" in request.args:
        flash(
            "You could not be logged into the portal: "
            + request.args.get("error_description"),
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
    id_token = tokens["userinfo"]

    session_tokens = {
        "access_token": tokens["access_token"],
        "id_token": tokens["id_token"],
    }

    session.update(
        tokens=session_tokens,
        is_authenticated=True,
        name=id_token.get("name", ""),
        email=id_token.get("email", ""),
        institution=id_token.get("organization", ""),
        sub=id_token.get("sub"),
    )

    if "identity_set" in id_token:
        identity_set = {_["email"] for _ in id_token["identity_set"]}
    else:
        identity_set = [id_token["email"]]

    for identity in identity_set:
        user = UserModel.find_by_email(identity)
        if user:
            session["user_id"] = user.id
            session["admin"] = user.admin
            session["email"] = identity
            return redirect(url_for("profile"))
    return redirect(url_for("create_profile"))
