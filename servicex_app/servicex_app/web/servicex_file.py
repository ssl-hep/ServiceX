from io import BytesIO
from textwrap import dedent
from urllib.parse import urlparse

import flask
from flask import (current_app, request, send_file, session)
from servicex_app.decorators import oauth_required
from servicex_app.models import UserModel


@oauth_required
def servicex_file():
    """Generate a servicex.yaml config file prepopulated with this endpoint."""
    code_gen_types = current_app.config.get('CODE_GEN_IMAGES', '').keys()
    sub = session.get('sub')
    user = UserModel.find_by_sub(sub)
    endpoint_url = get_correct_url(request)

    body = "api_endpoints:\n"
    for backend_type in code_gen_types:
        body += f"  - name: {backend_type}\n"
        body += f"    endpoint: {endpoint_url}\n"
        body += f"    token: {user.refresh_token}\n"
        body += f"    codegen: {backend_type}\n"
        body += "    return_data: root-file\n"
    return send_file(BytesIO(dedent(body).encode()), mimetype="text/plain",
                     as_attachment=True, download_name="servicex.yaml")


def get_correct_url(request: flask.Request) -> str:
    """
    Update url string to try to make sure that the proper url scheme (https, http)
    is used
    see https://github.com/ssl-hep/ServiceX/issues/266

    :param request: flask request object
    :return: string with http url changed to https except
    """

    parsed_url = urlparse(request.url_root)
    request_scheme = request.headers.get('X-Scheme')
    if request_scheme is not None:
        # use the same scheme that the request used
        return parsed_url._replace(scheme=request_scheme).geturl()
    elif parsed_url.scheme == "http" and "localhost" not in parsed_url.netloc:
        # if the request scheme is unknown use https unless we're referring
        # to localhost
        return parsed_url._replace(scheme="https").geturl()
    else:
        # give up and don't make any changes
        return request.url_root
