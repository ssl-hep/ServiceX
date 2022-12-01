from flask import current_app
from flask_jwt_extended import create_refresh_token
from globus_sdk import AccessTokenAuthorizer, AuthClient
from servicex.models import UserModel
from servicex.web.utils import load_app_client


def add_user(sub, email, name, organization, refresh_token):
    new_user = UserModel(
        sub=sub,
        email=email,
        name=name,
        institution=organization,
        refresh_token=refresh_token)

    if new_user.email == current_app.config.get('JWT_ADMIN'):
        new_user.admin = True
    new_user.pending = False
    try:
        new_user.save_to_db()
    except Exception as ex:
        print(str(ex))
