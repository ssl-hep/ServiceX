from flask import current_app
from flask_jwt_extended import create_refresh_token
from globus_sdk import AccessTokenAuthorizer, AuthClient
from servicex.models import UserModel
from servicex.web.utils import load_app_client


def add_user(code):
    ac = AuthClient(authorizer=AccessTokenAuthorizer(code))
    id_token = ac.oauth2_userinfo()

    tokens = tokens.by_resource_server,

    new_user = UserModel(
        sub=id_token.get('sub'),
        email=id_token.get('email', ''),
        name=id_token.get('name', ''),
        institution=id_token.get('organization', ''),
        refresh_token=create_refresh_token(identity=id_token.get('sub')))

    if new_user.email == current_app.config.get('JWT_ADMIN'):
        new_user.admin = True
    new_user.pending = False
    try:
        new_user.save_to_db()
    except Exception as ex:
        print(str(ex))
