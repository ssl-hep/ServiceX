import itertools

from flask import render_template, session
from flask_restful import reqparse
from flask_sqlalchemy import Pagination


from servicex.models import TransformRequest

model_attributes = {
    "start": TransformRequest.submit_time,
    "finish": TransformRequest.finish_time,
    "status": TransformRequest.status
}
parser = reqparse.RequestParser()
parser.add_argument("page", default=1, type=int)
sort_choices = tuple(model_attributes.keys())
parser.add_argument(
    "sort",
    choices=sort_choices,
    default="finish",
    help=f"Sort must be one of: {', '.join(map(repr, sort_choices))}."
)
order_choices = ("asc", "desc")
parser.add_argument(
    "order",
    choices=order_choices,
    default="desc",
    help="Order must be 'asc' or 'desc'."
)


def dashboard(template_name: str, user_specific=False):
    args = parser.parse_args()
    sort, order = args["sort"], args["order"]
    query = TransformRequest.query
    if user_specific:
        query = query.filter_by(submitted_by=session["user_id"])
    pagination: Pagination = query \
        .order_by(getattr(model_attributes[sort], order)()) \
        .paginate(page=args["page"], per_page=15, error_out=False)
    return render_template(
        template_name,
        pagination=pagination,
        dropdown_options=list(itertools.product(sort_choices, order_choices)),
        active_sort=sort,
        active_order=order
    )
