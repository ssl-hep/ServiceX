from flask import request, current_app, jsonify

from servicex_app.models import UserModel
from .utils import load_oauth_client
from flask_jwt_extended import create_refresh_token
import requests


def device_flow_info():
    """
    Gives the information clients need for the device workflow
    """
    if (client := current_app.config.get("OAUTH_DEVICE_FLOW_CLIENT_ID")) is None or (
        url := current_app.config.get("OAUTH_METADATA_URL")
    ) is None:
        return "Device auth flow not configured", 404
    return jsonify({"client": client, "config": url})


def bearer_token_exchange():
    """
    Given a bearer token, sets up the user account if needed and returns the associated
    ServiceX JWT.
    """

    if "Authorization" not in request.headers:
        return "No bearer token provided", 403

    oauth = load_oauth_client()
    res = requests.get(
        oauth.oauth.load_server_metadata()["userinfo_endpoint"],
        headers={"Authorization": request.headers["Authorization"]},
    )
    id_token = res.json()

    # Globus protection
    if "identity_set" in id_token:
        identity_set = {_["email"] for _ in id_token["identity_set"]}
    else:
        identity_set = [id_token["email"]]

    for identity in identity_set:
        user = UserModel.find_by_email(identity)
        if user:
            # we found an existing user
            return jsonify({"jwt": user.refresh_token, "pending": user.pending})

    # identity not in system yet
    identity = next(iter(identity_set))
    if identity == "":
        return "Unable to determine email of user", 403

    user = UserModel(
        sub=id_token.get("sub"),
        email=id_token.get("email", ""),
        name=id_token.get("name", ""),
        institution=id_token.get("organization", ""),
        experiment="",
        refresh_token=create_refresh_token(identity=identity),
    )
    if current_app.config.get("OAUTH_ALLOW_ALL_AFTER_AUTH"):
        user.pending = False
    if user.email == current_app.config.get("JWT_ADMIN"):
        user.admin = True
        user.pending = False
    user.save_to_db()

    return jsonify({"jwt": user.refresh_token, "pending": user.pending})
