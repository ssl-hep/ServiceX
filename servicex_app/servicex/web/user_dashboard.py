from flask import render_template, request, session
from flask_sqlalchemy import Pagination

from servicex.decorators import oauth_required
from servicex.models import TransformRequest


@oauth_required
def user_dashboard():
    page = request.args.get('page', 1, type=int)
    pagination: Pagination = TransformRequest.query\
        .filter_by(submitted_by=session["user_id"])\
        .order_by(TransformRequest.id.desc())\
        .paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "user_dashboard.html",
        transformation_requests=pagination.items,
        pagination=pagination
    )
