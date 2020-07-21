import json


def signup(email) -> str:
    text_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"New signup from {email}"
        }
    }
    approve_btn = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "Approve"
        },
        "style": "primary",
        "action_id": "accept_user",
        "value": f"{email}"
    }
    reject_btn = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "Reject"
        },
        "style": "danger",
        "action_id": "reject_user",
        "value": f"{email}"
    }
    actions_block = {
        "type": "actions",
        "elements": [approve_btn, reject_btn]
    }
    return json.dumps({
        "blocks": [text_block, actions_block],
        "text": f"New signup from {email}."
    })


def signup_ia(original_msg, initiating_user, action_id) -> str:
    action = "Approved" if action_id == "accept_user" else "Denied"
    feedback = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{action} by <@{initiating_user['id']}>"
            }
        ]
    }
    return json.dumps({
        "blocks": [original_msg['blocks'][0], feedback],
        "replace_original": True
    })
