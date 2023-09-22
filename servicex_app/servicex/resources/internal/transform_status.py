from datetime import datetime, timezone

from flask import current_app, request
from servicex.models import TransformRequest, db
from servicex.resources.servicex_resource import ServiceXResource


# # Status Updates POST
# status_parser = reqparse.RequestParser()
# status_parser.add_argument('timestamp', help='This field cannot be blank',
#                            required=True)
# status_parser.add_argument('severity', help='Should be debug, info, warn, or fatal',
#                            required=False)
# status_parser.add_argument('info', required=False)
# status_parser.add_argument('source', required=False)


class TransformationStatusInternal(ServiceXResource):
    def post(self, request_id):
        current_app.logger.info("--- Transformation Status Update Received ---")
        status = request.get_json()
        print(status)
        current_app.logger.info(f"--{status.info}--")
        if status.severity == "fatal":
            current_app.logger.error(f"Fatal error reported from "
                                     f"{status.source}: {status.info}",
                                     extra={'requestId': request_id})

            submitted_request = TransformRequest.lookup(request_id)
            submitted_request.status = 'Fatal'
            submitted_request.finish_time = datetime.now(tz=timezone.utc)
            submitted_request.failure_description = status.info
            submitted_request.save_to_db()
            db.session.commit()
        else:
            current_app.logger.info("Transformation Status Update", extra={
                                    'requestId': request_id, 'metric': status})
