from flask import render_template, abort

from servicex_app.decorators import oauth_required
from servicex_app.models import Dataset


@oauth_required
def dataset(id_: int):
    ds = Dataset.find_by_id(id_)
    if not ds:
        abort(404)
    return render_template("dataset.html", ds=ds)
