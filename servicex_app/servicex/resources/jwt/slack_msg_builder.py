import json

from slackblocks import ActionsBlock, SectionBlock, Button, Message


def signup(username) -> str:
    text_section = SectionBlock(f"New signup from {username}")
    approve_btn = Button("Approve", action_id="accept_user", value=username, style="primary")
    reject_btn = Button("Reject", action_id="reject_user", value=username, style="danger")
    actions = ActionsBlock([approve_btn, reject_btn])
    alt_text = f"New signup from {username}."
    return Message(channel='', text=alt_text, blocks=[text_section, actions]).json()


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
