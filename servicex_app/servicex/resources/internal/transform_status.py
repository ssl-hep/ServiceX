from datetime import datetime, timezone

from flask import current_app, request
from servicex.models import TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource


class TransformationStatusInternal(ServiceXResource):
    def post(self, request_id):
        current_app.logger.info("--- Transformation Status Update Received ---")

        status = request.get_json()
        if 'severity' not in status:
            status['severity'] = 'info'
        if 'source' not in status or 'info' not in status:
            return 'bad status', 400

        current_app.logger.info(f"--{status['info']}--")
        if status['severity'] == "fatal":
            current_app.logger.error(f"Fatal error reported from "
                                     f"{status['source']}: {status['info']}",
                                     extra={'requestId': request_id})

            submitted_request = TransformRequest.lookup(request_id)
            submitted_request.status = 'Fatal'
            submitted_request.finish_time = datetime.now(tz=timezone.utc)
            submitted_request.failure_description = status["info"]
            submitted_request.save_to_db()
            db.session.commit()
        else:
            current_app.logger.info("Transformation Status Update", extra={
                                    'requestId': request_id, 'metric': status})
