from flask import current_app
import globus_sdk
from cryptography.hazmat.primitives import serialization


def load_app_client():
    client_id = current_app.config['GLOBUS_CLIENT_ID']
    client_secret = current_app.config['GLOBUS_CLIENT_SECRET']
    return globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)


def refresh_cern_public_key():
    key_cache = current_app.extensions["KEY_CACHE"]
    public_key = key_cache.getkeyinfo(current_app.config.get("JWT_ISSUER"), key_id="rsa2")
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    current_app.config["JWT_PUBLIC_KEY"] = pem
