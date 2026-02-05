from enum import Enum
from flask import current_app
import re


class LogLevel(str, Enum):
    r"""
    Level of the log messages: INFO & ERROR
    This controls the log level of the logs displayed in the dashboard
    """

    info = "INFO"
    error = "ERROR"


def add_query(key, value):
    """
    Creates query string from the key and value pairs for use in constructing
    the kibana link
    """
    query_string = "(query:(match_phrase:({0}:'{1}')))".format(key, value)
    return query_string


def create_kibana_link_parameters(
    transform_id=None,
    log_level=LogLevel.info,
):
    """
    Construct n url for the kibana dashboard based on the input parameters
    """
    assert log_level and log_level in LogLevel, "Log level must be one of INFO or ERROR"
    log_url = current_app.config["LOGS_URL"]
    a_parameter = (
        f"&_a=(filters:!({add_query('requestId', transform_id)},"
        f"{add_query('level', str(log_level.value).lower())}))"
    )
    kibana_link = re.sub(r"&_g=\(\)", a_parameter, log_url)
    return kibana_link
