from io import BytesIO
from textwrap import dedent

from flask import current_app, flash, redirect, request, session, url_for, \
    send_file

from servicex.decorators import oauth_required
from servicex.models import UserModel


@oauth_required
def servicex_file():
    """Generate a .servicex config file prepopulated with this endpoint."""
    code_gen_image = current_app.config.get('CODE_GEN_IMAGE', "")
    candidates = ["xaod", "uproot", "miniaod", "nanoaod"]
    matches = [t for t in candidates if t in code_gen_image]
    if not matches or len(matches) > 1:
        msg = "Could not generate a .servicex config file. " \
              "Unable to infer filetype supported by this ServiceX instance."
        flash(msg, category='error')
        return redirect(url_for('profile'))
    backend_type = matches[0]
    sub = session.get('sub')
    user = UserModel.find_by_sub(sub)
    body = f"""\
    api_endpoints:
      - endpoint: {request.url_root}
        token: {user.refresh_token}
        type: {backend_type}
    """
    return send_file(BytesIO(dedent(body).encode()), mimetype="text/plain",
                     as_attachment=True, attachment_filename=".servicex")
