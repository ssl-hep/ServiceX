"""
Kibana URL Filter Modifier

This module provides functionality to add requestID filters to Kibana dashboard URLs.
"""

import re
import urllib.parse

from urllib.parse import urlunparse


def add_request_id_filter(url: str, request_id: str, log_level: str) -> str:
    """
    Add a filter to a Kibana dashboard URL to show only results for a given request ID
    with an ERROR level or higher.
    """
    decoded_url = urllib.parse.urlparse(url)

    view_match = re.search(r"/view/([^?]+)", decoded_url.fragment)
    instance_match = re.search(r"instance:([^)]+)", decoded_url.fragment)
    index_match = re.search(r"index:'([^']+)'", decoded_url.fragment)

    view = view_match.group(1) if view_match else None
    instance = instance_match.group(1) if instance_match else None
    index = index_match.group(1) if index_match else None

    # If we are unable to parse the fragment, return the original URL
    if view is None or instance is None or index is None:
        return url

    _a = f"(filters:!((query:(match_phrase:(instance:{instance}))),(query:(match_phrase:(requestId:'{request_id}'))),(query:(match_phrase:(level:{log_level})))),index:'{index}')"  # NOQA  E502

    new_fragment = f"/view/{view}?embed=true&_g=(filters:!(),refreshInterval:(pause:!t,value:1000),time:(from:now-24h/h,to:now))"  # NOQA  E502
    new_fragment += f"&_a={urllib.parse.quote(_a)}"
    decoded_url = decoded_url._replace(fragment=new_fragment)
    return urlunparse(decoded_url)
