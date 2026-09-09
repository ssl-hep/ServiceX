from datetime import datetime, timezone

from flask import current_app, request
from servicex_app.models import TransformRequest, TransformStatus
from servicex_app.resources.servicex_resource import ServiceXResource


class TransformationStatusInternal(ServiceXResource):
    def post(self, request_id):
        current_app.logger.info("--- Transformation Status Update Received ---")

        status = request.get_json()
        if "severity" not in status:
            status["severity"] = "info"
        if "source" not in status or "info" not in status:
            return "bad status", 400

        current_app.logger.info(f"--{status['info']}--")
        if status["severity"] == "fatal":
            current_app.logger.error(
                f"Fatal error reported from " f"{status['source']}: {status['info']}",
                extra={"request_id": request_id},
            )

            submitted_request = TransformRequest.lookup(request_id)
            if not submitted_request:
                msg = f"Transformation request not found with id: {request_id}"
                current_app.logger.error(msg, extra={"request_id": request_id})
                return {"message": msg}, 404

            submitted_request.status = TransformStatus.fatal
            submitted_request.finish_time = datetime.now(tz=timezone.utc)
            submitted_request.failure_description = status["info"]
            submitted_request.save_to_db()
        else:
            current_app.logger.info(
                "Transformation Status Update",
                extra={"request_id": request_id, "metric": status},
            )
