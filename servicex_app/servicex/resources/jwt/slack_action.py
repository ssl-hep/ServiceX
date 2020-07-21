import json
import requests
import sys
import traceback

from flask import request
from sqlalchemy.orm.exc import NoResultFound

from servicex.resources.servicex_resource import ServiceXResource
from servicex.models import UserModel
from .slack_msg_builder import signup_ia


class SlackAction(ServiceXResource):
    def post(self):
        is_verified, reject_message = self._verify_slack_request(request)
        if not is_verified:
            msg = f'Slack Verification Failed: {str(reject_message)}'
            return {'message': msg}, 401

        try:
            decoder = json.JSONDecoder()
            data = decoder.decode(request.form['payload'])

            action = data["actions"][0]
            initiating_user = data['user']
            original_msg = data['message']
            response_url = data["response_url"]

            action_id = action['action_id']
            if action_id == "accept_user":
                email = action['value']
                UserModel.accept(email)
                response = signup_ia(original_msg, initiating_user, action_id)
                slack_response = requests.post(response_url, response)
                slack_response.raise_for_status()
            elif action_id == "reject_user":
                # todo blocked by PR for delete-user endpoint
                raise NotImplementedError
        except NoResultFound as err:
            return {'message': str(err)}, 404
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': str(exc_value)}, 500
