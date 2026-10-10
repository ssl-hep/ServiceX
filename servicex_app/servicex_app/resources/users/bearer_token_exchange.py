# Copyright (c) 2026, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from flask import request, current_app, jsonify

from servicex_app.models import UserModel
from ...web.utils import load_oauth_client
from flask_jwt_extended import create_refresh_token
import requests
from servicex_app.reliable_requests import REQUEST_TIMEOUT, servicex_retry


def device_flow_info():
    """
    Gives the information clients need for the device workflow
    """
    if (client := current_app.config.get("OAUTH_DEVICE_FLOW_CLIENT_ID")) is None or (
        url := current_app.config.get("OAUTH_METADATA_URL")
    ) is None:
        return "Device auth flow not configured", 404
    return jsonify({"client": client, "config": url})


@servicex_retry()
def _get_userinfo(endpoint: str, headers: dict[str, str]) -> requests.Response:
    return requests.get(endpoint, headers=headers, timeout=REQUEST_TIMEOUT)


def bearer_token_exchange():
    """
    Given a bearer token, sets up the user account if needed and returns the associated
    ServiceX JWT.
    """

    if "Authorization" not in request.headers:
        return "No bearer token provided", 403

    oauth = load_oauth_client()
    res = _get_userinfo(oauth.oauth.load_server_metadata()["userinfo_endpoint"],
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
