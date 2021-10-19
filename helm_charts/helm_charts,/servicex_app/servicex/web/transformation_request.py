from flask import render_template, abort, current_app

from servicex.decorators import oauth_required
from servicex.models import TransformRequest


@oauth_required
def transformation_request(id_: str):
    current_app.logger.debug(f"Got transformation request: {id_}")
    req = TransformRequest.lookup(id_)
    if not req:
        abort(404)
    return render_template('transformation_request.html', req=req)
