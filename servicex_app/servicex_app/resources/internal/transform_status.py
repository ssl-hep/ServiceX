from datetime import datetime, timezone

from flask import current_app, request
from servicex_app.models import DatasetStatus, TransformRequest, db
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
            submitted_request.status = "Fatal"
            submitted_request.finish_time = datetime.now(tz=timezone.utc)
            submitted_request.failure_description = status["info"]
            submitted_request.save_to_db()
            db.session.commit()
        else:
            current_app.logger.info(
                "Transformation Status Update",
                extra={"request_id": request_id, "metric": status},
            )

    def get(self, request_id):
        """
        Return whether the transformer sidecars for this request can safely
        shut down. Sidecars poll this endpoint.
        """
        submitted_request = TransformRequest.lookup(request_id)
        if submitted_request is None:
            return {"message": f"Unknown request id: {request_id}"}, 404

        dataset = submitted_request.dataset
        lookup_complete = (
            dataset is not None and dataset.lookup_status == DatasetStatus.complete
        )
        return {
            "request_id": request_id,
            "status": submitted_request.status.string_name,
            "lookup_complete": lookup_complete,
            "files_remaining": submitted_request.files_remaining,
            "transform_complete": submitted_request.status.is_complete,
        }
