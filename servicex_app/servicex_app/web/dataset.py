from flask import render_template, abort, request

from servicex_app.decorators import oauth_required
from servicex_app.models import Dataset, LogMessage

# The dataset page shows its logs in a scrolling grid rather than pages, so
# cap how many of the newest records it renders.
MAX_DATASET_LOGS = 500


@oauth_required
def dataset(id_: int):
    ds = Dataset.find_by_id(id_)
    if not ds:
        abort(404)

    log_level = request.args.get("log_level", "").upper()
    # An unrecognized level is no filter at all, not an empty result.
    min_level = LogMessage.LEVELS.get(log_level)

    query = LogMessage.query.filter_by(dataset_id=ds.id)
    if min_level is None:
        log_level = None
    else:
        # The filter is a minimum severity: this level and everything above it.
        query = query.filter(LogMessage.level_no >= min_level)

    logs = query.order_by(LogMessage.timestamp.desc()).limit(MAX_DATASET_LOGS).all()

    return render_template(
        "dataset.html",
        ds=ds,
        logs=logs,
        log_levels=LogMessage.LEVELS,
        active_level=log_level,
        max_logs=MAX_DATASET_LOGS,
    )
