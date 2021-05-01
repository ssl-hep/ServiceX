from datetime import timedelta

from flask import render_template, abort
import humanize

from servicex.models import TransformRequest, db


def transformation_request(id_: str):
    print(id_)
    if id_.isnumeric():
        req = TransformRequest.query.get(id_)
    else:
        req = db.session.query(TransformRequest).filter_by(request_id=id_).one()
    print(req)
    if not req:
        abort(404)
    return render_template(
        'transformation_request.html', req=req, humanize=humanize, timedelta=timedelta
    )
