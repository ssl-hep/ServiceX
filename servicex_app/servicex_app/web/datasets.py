import itertools

from flask import render_template
from flask_restful import reqparse

from servicex_app.decorators import oauth_required
from servicex_app.models import Dataset

model_attributes = {
    "last_used": Dataset.last_used,
    "last_updated": Dataset.last_updated,
    "name": Dataset.name,
    "size": Dataset.size,
    "events": Dataset.events,
    "files": Dataset.n_files,
}
parser = reqparse.RequestParser()
parser.add_argument("page", default=1, type=int, location="args")
sort_choices = tuple(model_attributes.keys())
parser.add_argument(
    "sort",
    choices=sort_choices,
    default="last_used",
    location="args",
    help=f"Sort must be one of: {', '.join(map(repr, sort_choices))}.",
)
order_choices = ("asc", "desc")
parser.add_argument(
    "order",
    choices=order_choices,
    default="desc",
    location="args",
    help="Order must be 'asc' or 'desc'.",
)
parser.add_argument(
    "show_deleted",
    type=lambda v: str(v).lower() in ("1", "true", "yes", "on"),
    default=False,
    location="args",
)


@oauth_required
def datasets():
    args = parser.parse_args()
    sort, order = args["sort"], args["order"]
    query = Dataset.query
    if not args["show_deleted"]:
        query = query.filter_by(stale=False)

    sort_column = model_attributes[sort]
    sort_order = sort_column.asc() if order == "asc" else sort_column.desc()
    pagination = query.order_by(sort_order).paginate(
        page=args["page"], per_page=15, error_out=False
    )
    return render_template(
        "datasets.html",
        pagination=pagination,
        dropdown_options=list(itertools.product(sort_choices, order_choices)),
        active_sort=sort,
        active_order=order,
        show_deleted=args["show_deleted"],
    )
