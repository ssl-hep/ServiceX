from flask import redirect, url_for, current_app, session

from servicex.decorators import oauth_required
from .utils import load_app_client


@oauth_required
def sign_out():
    """Revoke tokens with Globus Auth and destroy session state."""

    # Revoke tokens with Globus Auth
    client = load_app_client()
    for token, _type in ((token_info[ty], ty)
                         for token_info in session['tokens'].values()
                         for ty in ('access_token', 'refresh_token')
                         if token_info[ty] is not None):
        client.oauth2_revoke_token(token,
                                   additional_params={'token_type_hint': _type})

    session.clear()

    redirect_uri = url_for('home', _external=True)
    ga_logout_url = ''.join([
        "https://auth.globus.org/v2/web/logout",
        f"?client={current_app.config['GLOBUS_CLIENT_ID']}",
        f"&redirect_uri={redirect_uri}",
        "&redirect_name=ServiceX Portal"
    ])
    return redirect(ga_logout_url)
