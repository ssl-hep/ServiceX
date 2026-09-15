import hashlib
import hmac
import json
import time
from urllib.parse import quote_plus

from flask import Response

from servicex_app.reliable_requests import REQUEST_TIMEOUT

from ...resource_test_base import ResourceTestBase

payload = {
    "type": "block_actions",
    "user": {
        "id": "slack-user-id",
        "username": "johndoe",
        "name": "John Doe",
        "team_id": "slack-team-id",
    },
    "api_app_id": "slack-app-id",
    "token": "slack-app-token",
    "container": {
        "type": "message",
        "message_ts": "1596519683.000100",
        "channel_id": "slack-channel-id",
        "is_ephemeral": False,
    },
    "trigger_id": "slack-trigger-id",
    "team": {"id": "slack-team-id", "domain": "slack-workspace"},
    "channel": {"id": "slack-channel-id", "name": "servicex"},
    "message": {
        "type": "message",
        "subtype": "bot_message",
        "text": "New signup from jane@example.com.",
        "ts": "1596519683.000100",
        "bot_id": "slack-bot-id",
        "blocks": [
            {
                "type": "section",
                "block_id": "jzHEC",
                "text": {
                    "type": "mrkdwn",
                    "text": "New signup from <mailto:jane@example.com|jane@example.com>",
                    "verbatim": False,
                },
            },
            {
                "type": "actions",
                "block_id": "QbQqw",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "accept_user",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve",
                            "emoji": True,
                        },
                        "style": "primary",
                        "value": "jane@example.com",
                    },
                    {
                        "type": "button",
                        "action_id": "reject_user",
                        "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                        "style": "danger",
                        "value": "jane@example.com",
                    },
                ],
            },
        ],
    },
    "response_url": "http://www.example.com",
    "actions": [
        {
            "action_id": "accept_user",
            "block_id": "QbQqw",
            "text": {"type": "plain_text", "text": "Approve", "emoji": True},
            "value": "jane@example.com",
            "style": "primary",
            "type": "button",
            "action_ts": "1596666622.160856",
        }
    ],
}


class TestSlackInteraction(ResourceTestBase):
    def test_slack_interaction_not_configured(self, mocker, client):
        mock_post = mocker.patch("requests.post")
        response: Response = client.post(
            "/slack", data={"payload": json.dumps(payload)}
        )
        assert response.status_code == 403
        with client.application.app_context():
            from servicex_app.web.slack_msg_builder import missing_slack_app

            mock_post.assert_called_once_with(
                payload["response_url"], missing_slack_app(), timeout=REQUEST_TIMEOUT
            )

    def test_slack_interaction_expired(self, mocker):
        mock_post = mocker.patch("requests.post")
        client = self._test_client(
            extra_config={"SLACK_SIGNING_SECRET": "my-slack-secret"}
        )
        headers = {"X-Slack_Request-Timestamp": 0}
        response: Response = client.post(
            "/slack", data={"payload": json.dumps(payload)}, headers=headers
        )
        assert response.status_code == 403
        with client.application.app_context():
            from servicex_app.web.slack_msg_builder import request_expired

            mock_post.assert_called_once_with(
                payload["response_url"], request_expired(), timeout=REQUEST_TIMEOUT
            )

    def test_slack_interaction_invalid(self, mocker):
        mock_post = mocker.patch("requests.post")
        client = self._test_client(
            extra_config={"SLACK_SIGNING_SECRET": "my-slack-secret"}
        )
        headers = {"X-Slack_Request-Timestamp": time.time(), "X-Slack-Signature": "abc"}
        response: Response = client.post(
            "/slack", data={"payload": json.dumps(payload)}, headers=headers
        )
        assert response.status_code == 401
        with client.application.app_context():
            from servicex_app.web.slack_msg_builder import verification_failed

            mock_post.assert_called_once_with(
                payload["response_url"], verification_failed(), timeout=REQUEST_TIMEOUT
            )

    def test_slack_interaction_accept_user(self, mocker):
        mock_post = mocker.patch("requests.post")
        mock_user_model = mocker.patch(
            "servicex_app.resources.users.slack_interaction.UserModel"
        )
        secret = "my-slack-secret"
        client = self._test_client(
            extra_config={"SLACK_SIGNING_SECRET": "my-slack-secret"}
        )
        timestamp = time.time()
        body = f"payload={quote_plus(json.dumps(payload), safe=',:@/')}"
        sig_basestring = f"v0:{timestamp}:{body}".encode("utf-8")
        signature = hmac.new(
            secret.encode("utf-8"), sig_basestring, digestmod=hashlib.sha256
        ).hexdigest()
        headers = {
            "X-Slack_Request-Timestamp": timestamp,
            "X-Slack-Signature": "v0=" + signature,
        }
        response: Response = client.post(
            "/slack", data={"payload": json.dumps(payload)}, headers=headers
        )
        assert response.status_code == 200
        email = payload["actions"][0]["value"]
        mock_user_model.accept.assert_called_once_with(email)
        with client.application.app_context():
            from servicex_app.web.slack_msg_builder import signup_ia

            resp = signup_ia(payload["message"], payload["user"], "accept_user")
            mock_post.assert_called_once_with(
                payload["response_url"], resp, timeout=REQUEST_TIMEOUT
            )
