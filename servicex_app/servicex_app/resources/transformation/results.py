import logging
import datetime

from flask_restful import reqparse

from servicex_app.decorators import auth_required
from servicex_app.models import TransformationResult
from servicex_app.resources.servicex_resource import ServiceXResource

logger = logging.getLogger(__name__)


class TransformationResults(ServiceXResource):
    @auth_required
    def get(self, request_id):
        if not request_id:
            return {"message": "Missing required transformation request_id"}, 400

        parser = reqparse.RequestParser()
        parser.add_argument(
            'begin_at',
            type=str,
            required=False,
            location='args'
        )

        args = parser.parse_args()

        transform_result_query = TransformationResult.query.filter_by(request_id=request_id)

        begin_at_str = args.get('begin_at')
        if begin_at_str:
            try:
                begin_at = datetime.datetime.fromisoformat(begin_at_str)
            except AttributeError:
                return {"message": f"begin_at value {begin_at_str} is not an ISO 8601 compliant datetime"}, 400
            transform_result_query = transform_result_query.filter(TransformationResult.created_at > begin_at)

        results = [transformation_result.to_json(transformation_result) for transformation_result in transform_result_query]

        return {
            "results": results
        }
