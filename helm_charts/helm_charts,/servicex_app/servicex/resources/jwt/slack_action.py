import json
import traceback
import requests
import sys

from flask import request
from flask_restful import reqparse

from servicex.resources.servicex_resource import ServiceXResource
from servicex.resources.jwt.utils import accept_user

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)


class SlackAction(ServiceXResource):
    def post(self):
        is_verified, reject_message = self._verify_slack_request(request)
        if not is_verified:
            return {'message': f'Slack Verification Failed: {str(reject_message)}'}, 401
        else:
            try:
                decoder = json.JSONDecoder()
                data = decoder.decode(request.form['payload'])

                action = data["actions"][0]
                initiating_user = data['user']
                original_msg = data['message']
                response_url = data["response_url"]

                action_id = action['action_id']
                if action_id == "accept_user":
                    username = action['value']
                    accept_user(username)
                    feedback = {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Approved by <@{initiating_user['id']}>"
                            }
                        ]
                    }
                    response_msg = {
                        "blocks": [original_msg['blocks'][0], feedback],
                        "replace_original": True
                    }
                    slack_response = requests.post(response_url, json.dumps(response_msg))
                    slack_response.raise_for_status()
                elif action_id == "reject_user":
                    # todo blocked by PR for delete-user endpoint
                    pass
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                print(exc_value)
                return {'message': str(exc_value)}, 500
