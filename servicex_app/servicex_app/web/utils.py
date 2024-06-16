from flask import current_app
import globus_sdk


def load_app_client():
    client_id = current_app.config['GLOBUS_CLIENT_ID']
    client_secret = current_app.config['GLOBUS_CLIENT_SECRET']
    return globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
