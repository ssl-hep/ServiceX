from flask import render_template, request
from flask_sqlalchemy.pagination import Pagination
from servicex_app.decorators import oauth_required
from servicex_app.models import TransformationResult
from servicex_app.resources.servicex_resource import ServiceXResource


@oauth_required
def transformation_results(id_: str):
    treq = ServiceXResource.get_owned_request(id_)
    page = request.args.get("page", 1, type=int)
    filter_by_values = {}
    status = request.args.get("status")
    if status:
        filter_by_values["transform_status"] = status
    pagination: Pagination = (
        TransformationResult.query.filter_by(
            request_id=treq.request_id, **filter_by_values
        )
        .order_by(TransformationResult.file_id.asc())
        .paginate(page=page, per_page=100, error_out=False)
    )
    return render_template(
        "transformation_results.html", treq=treq, pagination=pagination
    )
