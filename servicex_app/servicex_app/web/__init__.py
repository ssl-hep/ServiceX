from flask import current_app
from .kibana_url_filter import filter_kibana_url


def create_kibana_link(transform_id=None, log_level="INFO"):
    log_url = current_app.config["LOGS_URL"]
    return filter_kibana_url(log_url, transform_id, log_level)
