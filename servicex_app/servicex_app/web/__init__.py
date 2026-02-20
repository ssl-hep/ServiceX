from flask import current_app
from .kibana_url_filter import add_request_id_filter


def create_kibana_link(transform_id=None, log_level="INFO"):
    log_url = current_app.config["LOGS_URL"]
    return add_request_id_filter(log_url, transform_id, log_level)
