from flask import (flash, request, redirect, url_for, session, current_app, make_response)

from servicex.models import UserModel
from .utils import load_app_client

from globus_sdk import AuthClient, AccessTokenAuthorizer
from flask_jwt_extended import (get_jwt_identity,
                                verify_jwt_in_request)

from flask_jwt_extended.exceptions import NoAuthorizationError


def auth_callback():
    """Handles the interaction with Globus Auth."""
    if 'error' in request.args:
        flash("You could not be logged into the portal: "
              + request.args.get('error_description'),
              request.args['error'])
        return redirect('/')
    scheme = 'http' if 'localhost' in request.base_url else 'https'

    deployment_type = current_app.config.get('AUTH_TYPE')

    if deployment_type == 'jwt':
        jwt_header = request.headers.get('Authorization')
        if jwt_header:
            try:
                (_, jwt_data) = verify_jwt_in_request(locations=["headers"])

                jwt_val = get_jwt_identity()
                user = UserModel.find_by_sub(jwt_val)

                if not user:
                    new_user = UserModel(
                            sub=jwt_data.get('sub', None),
                            email=jwt_data.get('email', None),
                            name=jwt_data.get('name', None),
                            institution=jwt_data.get('institution', None),
                            admin=jwt_data.get('admin', False),
                            id=jwt_data.get('id'),
                            experiment=jwt_data.get('experiment', None),
                            pending=False
                            )

                    new_user.save_to_db()

                session.update(
                    tokens=[{'access_token': jwt_header}],
                    is_authenticated=True,
                    name=jwt_data.get('name', None),
                    email=jwt_data.get('email', None),
                    institution=jwt_data.get('institution', None),
                    sub=jwt_data.get('sub', None),
                    admin=jwt_data.get('admin', False),
                    id=jwt_data.get('id')
                )

                return redirect(url_for('user-dashboard'))

            except NoAuthorizationError as exc:
                return make_response({'message': str(exc)}, 401)

    else:
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
        auth_tokens = tokens.by_resource_server["auth.globus.org"]
        ac = AuthClient(authorizer=AccessTokenAuthorizer(auth_tokens["access_token"]))
        id_token = ac.oauth2_userinfo()

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
