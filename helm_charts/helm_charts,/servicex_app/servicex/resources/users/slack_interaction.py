import hashlib
import hmac
import json
import time

import requests
from flask import request, current_app, Response
from sqlalchemy.orm.exc import NoResultFound

from servicex.resources.servicex_resource import ServiceXResource
from servicex.models import UserModel
from servicex.web.slack_msg_builder import signup_ia, missing_slack_app, request_expired, \
    verification_failed, user_not_found


def respond(url, message):
    slack_response = requests.post(url, message)
    slack_response.raise_for_status()


class SlackInteraction(ServiceXResource):
    def post(self) -> Response:
        body = request.get_data().decode('utf-8')
        decoder = json.JSONDecoder()
        data = decoder.decode(request.form['payload'])
        response_url = data["response_url"]

        secret = current_app.config.get('SLACK_SIGNING_SECRET')
        if not secret:
            current_app.logger.error("Slack interaction received but no Slack app configured")
            respond(response_url, missing_slack_app())
            return Response(status=403)

        timestamp = request.headers['X-Slack-Request-Timestamp']
        if abs(time.time() - float(timestamp) > 60 * 5):
            respond(response_url, request_expired())
            return Response(status=403)

        sig_basestring = f"v0:{timestamp}:{body}".encode('utf-8')
        signature = "v0=" + hmac.new(secret.encode('utf-8'),
                                     sig_basestring,
                                     digestmod=hashlib.sha256).hexdigest()
        slack_signature = request.headers['X-Slack-Signature']
        if not hmac.compare_digest(signature, slack_signature):
            respond(response_url, verification_failed())
            return Response(status=401)

        action = data["actions"][0]
        initiating_user = data['user']
        original_msg = data['message']
        action_id = action['action_id']
        if action_id == "accept_user":
            email = action['value']
            try:
                UserModel.accept(email)
            except NoResultFound as err:
                respond(response_url, user_not_found(str(err)))
                return Response(status=404)
            response_msg = signup_ia(original_msg, initiating_user, action_id)
            slack_response = requests.post(response_url, response_msg)
            slack_response.raise_for_status()
        elif action_id == "reject_user":
            # todo blocked by PR for delete-user endpoint
            raise NotImplementedError
        return Response(status=200)
