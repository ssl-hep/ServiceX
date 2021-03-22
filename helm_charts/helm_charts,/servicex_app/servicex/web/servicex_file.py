from io import BytesIO
from textwrap import dedent
from urllib.parse import urlparse

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
        flash(msg, category='error')
        return redirect(url_for('profile'))
    backend_type = matches[0]
    sub = session.get('sub')
    user = UserModel.find_by_sub(sub)

    endpoint_url = correct_url(request.url_root)
    body = f"""\
    api_endpoints:
      - endpoint: {endpoint_url}
        token: {user.refresh_token}
        type: {backend_type}
    """
    return send_file(BytesIO(dedent(body).encode()), mimetype="text/plain",
                     as_attachment=True, attachment_filename="servicex.yaml")


def correct_url(url: str) -> str:
    """
    Update url string to remove http reference in uri to https reference
    unless the url refers to localhost
    see https://github.com/ssl-hep/ServiceX/issues/266

    :param url: string with complete url
    :return: string with http url changed to https except
    """

    parsed_url = urlparse(url)
    if parsed_url.scheme == "http" and "localhost" not in parsed_url.netloc:
        return parsed_url._replace(scheme="https").geturl()
    else:
        return url
