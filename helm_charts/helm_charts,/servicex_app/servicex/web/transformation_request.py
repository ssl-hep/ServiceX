from flask import render_template, abort

from servicex.decorators import oauth_required
from servicex.models import TransformRequest


@oauth_required
def transformation_request(id_: str):
    req = TransformRequest.lookup(id_)
    if not req:
        abort(404)
    return render_template('transformation_request.html', req=req)
