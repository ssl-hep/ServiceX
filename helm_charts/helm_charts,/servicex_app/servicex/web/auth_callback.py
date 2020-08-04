from typing import Optional

from flask import flash, request, redirect, url_for, session
from sqlalchemy.orm.exc import NoResultFound

from servicex.models import UserModel
from .utils import load_app_client


def auth_callback():
    """Handles the interaction with Globus Auth."""
    if 'error' in request.args:
        flash("You could not be logged into the portal: "
              + request.args.get('error_description'),
              request.args['error'])
        return redirect('/')

    redirect_uri = url_for('auth_callback', _external=True)

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
    print("ID Token", id_token)

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
    print("Identity set", identity_set)

    user: Optional[UserModel] = None
    for identity in identity_set:
        try:
            user = UserModel.find_by_sub(identity)
            session['user_id'] = user.id
            session['admin'] = user.admin
        except NoResultFound as err:
            print(err)
    if user:
        return redirect(url_for('profile'))
    else:
        return redirect(url_for('create_profile'))
