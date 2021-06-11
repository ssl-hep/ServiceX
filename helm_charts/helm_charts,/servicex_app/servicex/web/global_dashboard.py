from flask import render_template, request
from flask_sqlalchemy import Pagination

from servicex.decorators import admin_required
from servicex.models import TransformRequest


@admin_required
def global_dashboard():
    page = request.args.get('page', 1, type=int)
    pagination: Pagination = TransformRequest.query\
        .order_by(TransformRequest.finish_time.desc(), TransformRequest.submit_time.desc())\
        .paginate(page=page, per_page=25, error_out=False)
    return render_template("global_dashboard.html", pagination=pagination)
