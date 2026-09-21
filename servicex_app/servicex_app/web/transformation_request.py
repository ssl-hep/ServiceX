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
    log_level = request.args.get("log_level", "").upper()
    if log_level not in LOG_LEVELS:
        log_level = None

    query = LogMessage.query.filter_by(request_id=req.request_id)
    if log_level:
        # LOG_LEVELS is ordered least to most severe, so everything from the
        # selected level onward is "this level and above".
        query = query.filter(
            LogMessage.level.in_(LOG_LEVELS[LOG_LEVELS.index(log_level) :])
        )

    logs = query.order_by(LogMessage.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template(
        "transformation_request.html",
        req=req,
        logs=logs,
        log_levels=LOG_LEVELS,
        active_level=log_level,
    )
