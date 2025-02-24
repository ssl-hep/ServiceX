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
        server_metadata_url=current_app.config['OAUTH_CLIENT_ID'],
        client_id=current_app.config['OAUTH_CLIENT_ID'],
        client_secret=current_app.config['OAUTH_CLIENT_SECRET'],
        client_kwargs={'scope': 'openid profile email'}
    )
#    oauth.register(
#        name='oauth',
#        server_metadata_url='https://keycloak-dev.tempest.uchicago.edu/realms/servicey/.well-known/openid-configuration',
#        client_id='servicey-client',
#        client_secret='MTscoN6ZpQnxXY1lpTwWkmuygd7jJzWI',
#        client_kwargs={'scope': 'openid profile email'}
#    )
    oauth.init_app(current_app)
    return oauth


def load_app_client():
    client_id = current_app.config['OAUTH_CLIENT_ID']
    client_secret = current_app.config['OAUTH_CLIENT_SECRET']
    return globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
