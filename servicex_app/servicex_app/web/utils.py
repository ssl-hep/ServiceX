from flask import current_app
import globus_sdk
from authlib.integrations.flask_client import OAuth

oauth = None


def load_oauth_client():
    global oauth
    if oauth is not None:
        return oauth
    oauth = OAuth()
    oauth.register(
        name='oauth',
        server_metadata_url=current_app.config['OAUTH_METADATA_URL'],
        client_id=current_app.config['OAUTH_CLIENT_ID'],
        client_secret=current_app.config['OAUTH_CLIENT_SECRET'],
        client_kwargs={'scope': 'openid profile email'}
    )
    oauth.init_app(current_app)
    return oauth


def load_app_client():
    client_id = current_app.config['OAUTH_CLIENT_ID']
    client_secret = current_app.config['OAUTH_CLIENT_SECRET']
    return globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
