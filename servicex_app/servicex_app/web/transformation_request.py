from flask import render_template, abort, current_app, request

from servicex_app.decorators import oauth_required
from servicex_app.models import TransformRequest, LogMessage


@oauth_required
def transformation_request(id_: str):
    current_app.logger.debug(f"Got transformation request: {id_}")
    req = TransformRequest.lookup(id_)
    if not req:
        abort(404)

    page = request.args.get("page", 1, type=int)
    log_level = request.args.get("log_level", "").upper()
    # An unrecognized level is no filter at all, not an empty result.
    min_level = LogMessage.LEVELS.get(log_level)
    if min_level is None:
        log_level = None

    query = LogMessage.query.filter_by(request_id=req.request_id)
    if min_level is not None:
        # The filter is a minimum severity: this level and everything above it.
        query = query.filter(LogMessage.level_no >= min_level)

    logs = query.order_by(LogMessage.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template(
        "transformation_request.html",
        req=req,
        logs=logs,
        log_levels=LogMessage.LEVELS,
        active_level=log_level,
    )
