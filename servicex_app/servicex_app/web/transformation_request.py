from flask import render_template, abort, current_app

from servicex_app.decorators import oauth_required
from servicex_app.models import TransformRequest
from servicex_app.web.utils import user_owns_request


@oauth_required
def transformation_request(id_: str):
    current_app.logger.debug(f"Got transformation request: {id_}")
    req = TransformRequest.lookup(id_)
    if not req:
        abort(404)
    if not user_owns_request(req):
        abort(403)
    return render_template("transformation_request.html", req=req)
