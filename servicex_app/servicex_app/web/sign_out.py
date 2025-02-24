from flask import redirect, url_for, current_app, session

from servicex_app.decorators import oauth_required
from .utils import load_app_client, load_oauth_client


@oauth_required
def sign_out():
    """Revoke tokens with Globus Auth and destroy session state."""
    from authlib.integrations.requests_client import OAuth2Session
    # Revoke tokens with Globus Auth
    # client = load_app_client()
    # for token, _type in ((token_info[ty], ty)
    #                      for token_info in session['tokens'].values()
    #                      for ty in ('access_token', 'refresh_token')
    #                      if token_info[ty] is not None):
    #     client.oauth2_revoke_token(token, body_params={'token_type_hint': _type})
    oauth = load_oauth_client()
    client = OAuth2Session(oauth.oauth.client_id, oauth.oauth.client_secret,
                           scope=oauth.oauth.client_kwargs['scope'])
    oauth.oauth.load_server_metadata()
    print(oauth.oauth.server_metadata)
    for ty in ('access_token', 'refresh_token'):
        if ty in session['tokens']:
            client.revoke_token(oauth.oauth.server_metadata['revocation_endpoint'],
                                token=session['tokens'][ty])

    session.clear()

    redirect_uri = url_for('home', _external=True)
    if 'end_session_endpoint' in oauth.oauth.server_metadata:
        ga_logout_url = ''.join([
            oauth.oauth.server_metadata['end_session_endpoint'],
            f"?client={current_app.config['OAUTH_CLIENT_ID']}",
            f"&redirect_uri={redirect_uri}",
            "&redirect_name=ServiceX Portal"
        ])
        return redirect(ga_logout_url)
    else:
        # if metadata doesn't give us the relevant endpoint (e.g. Globus)
        return redirect(redirect_uri)
