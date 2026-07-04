from flask import render_template, abort, current_app, request

from servicex_app.decorators import oauth_required
from servicex_app.models import TransformRequest, LogMessage

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@oauth_required
def transformation_request(id_: str):
    current_app.logger.debug(f"Got transformation request: {id_}")
    req = TransformRequest.lookup(id_)
    if not req:
        abort(404)

    page = request.args.get("page", 1, type=int)
    log_level = request.args.get("log_level")
    filter_by_values = {}
    if log_level:
        filter_by_values["level"] = log_level

    logs = (
        LogMessage.query.filter_by(request_id=req.request_id, **filter_by_values)
        .order_by(LogMessage.timestamp.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )

    return render_template(
        "transformation_request.html",
        req=req,
        logs=logs,
        log_levels=LOG_LEVELS,
        active_level=log_level,
    )
