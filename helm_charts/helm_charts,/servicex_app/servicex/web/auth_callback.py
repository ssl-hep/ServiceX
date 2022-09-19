from flask import flash, request, redirect, url_for, session

from servicex.models import UserModel
from .utils import load_app_client


def auth_callback():
    """Handles the interaction with Globus Auth."""
    if 'error' in request.args:
        flash("You could not be logged into the portal: "
              + request.args.get('error_description'),
              request.args['error'])
        return redirect('/')
    scheme = 'http' if 'localhost' in request.base_url else 'https'
    redirect_uri = url_for('auth_callback', _external=True, _scheme=scheme)

    client = load_app_client()
    client.oauth2_start_flow(redirect_uri, refresh_tokens=True)

    # If there's no "code" query string param, start a Globus Auth login flow
    if 'code' not in request.args:
        auth_uri = client.oauth2_get_authorize_url()
        return redirect(auth_uri)

    # Otherwise, we're coming back from Globus Auth with a code
    code = request.args.get('code')
    tokens = client.oauth2_exchange_code_for_tokens(code)
    id_token = tokens.decode_id_token(client)

    session.update(
        tokens=tokens.by_resource_server,
        is_authenticated=True,
        name=id_token.get('name', ''),
        email=id_token.get('email', ''),
        institution=id_token.get('organization', ''),
        sub=id_token.get('sub')
    )

    access_token = session['tokens']['auth.globus.org']['access_token']
    token_introspect = client.oauth2_token_introspect(token=access_token,
                                                      include="identity_set")
    identity_set = token_introspect.data["identity_set"]

    for identity in identity_set:
        user = UserModel.find_by_sub(identity)
        if user:
            session['user_id'] = user.id
            session['admin'] = user.admin
            return redirect(url_for('user-dashboard'))
    return redirect(url_for('create_profile'))
