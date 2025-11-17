from flask import redirect, url_for, current_app, session

from servicex_app.decorators import oauth_required
from .utils import load_oauth_client


@oauth_required
def sign_out():
    """Revoke tokens with OIDC and destroy session state."""
    from authlib.integrations.requests_client import OAuth2Session

    oauth = load_oauth_client()
    client = OAuth2Session(
        oauth.oauth.client_id,
        oauth.oauth.client_secret,
        scope=oauth.oauth.client_kwargs["scope"],
    )
    oauth.oauth.load_server_metadata()
    id_token = session["tokens"].get("id_token")
    for ty in ("access_token",):
        if ty in session["tokens"]:
            client.revoke_token(
                oauth.oauth.server_metadata["revocation_endpoint"],
                token=session["tokens"][ty],
            )

    session.clear()

    redirect_uri = url_for("home", _external=True)
    if "end_session_endpoint" in oauth.oauth.server_metadata:
        ga_logout_url = "".join(
            [
                oauth.oauth.server_metadata["end_session_endpoint"],
                f"?client_id={current_app.config['OAUTH_CLIENT_ID']}",
                f"&id_token_hint={id_token}" if id_token else "",
                f"&post_logout_redirect_uri={redirect_uri}",
            ]
        )
        return redirect(ga_logout_url)
    else:
        # if metadata doesn't give us the relevant endpoint (e.g. Globus)
        return redirect(redirect_uri)
