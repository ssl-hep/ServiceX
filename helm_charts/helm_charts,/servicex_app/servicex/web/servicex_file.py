from io import BytesIO
from textwrap import dedent
from urllib.parse import urlparse

import flask
from flask import current_app, flash, redirect, request, session, url_for, \
    send_file

from servicex.decorators import oauth_required
from servicex.models import UserModel


@oauth_required
def servicex_file():
    """Generate a servicex.yaml config file prepopulated with this endpoint."""
    code_gen_image = current_app.config.get('CODE_GEN_IMAGE', "")
    candidates = ["xaod", "uproot", "miniaod", "nanoaod"]
    matches = [t for t in candidates if t in code_gen_image]
    if not matches or len(matches) > 1:
        msg = "Could not generate a servicex.yaml config file. " \
              "Unable to infer filetype supported by this ServiceX instance."
        current_app.logger.error(msg)
        flash(msg, category='error')
        return redirect(url_for('profile'))
    backend_type = matches[0]
    sub = session.get('sub')
    user = UserModel.find_by_sub(sub)

    endpoint_url = get_correct_url(request)
    body = f"""\
    api_endpoints:
      - name: {backend_type}
        endpoint: {endpoint_url}
        token: {user.refresh_token}
        type: {backend_type}
    """
    return send_file(BytesIO(dedent(body).encode()), mimetype="text/plain",
                     as_attachment=True, attachment_filename="servicex.yaml")


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
