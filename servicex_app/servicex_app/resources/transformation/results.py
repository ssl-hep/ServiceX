import datetime

from flask_restful import reqparse

from servicex_app.decorators import auth_required
from servicex_app.models import TransformationResult
from servicex_app.resources.servicex_resource import ServiceXResource


class TransformationResults(ServiceXResource):
    @auth_required
    def get(self, request_id):
        if not request_id:
            return {"message": "Missing required transformation request_id"}, 400

        parser = reqparse.RequestParser()
        parser.add_argument("later_than", type=str, required=False, location="args")

        args = parser.parse_args()

        transform_result_query = TransformationResult.query.filter_by(
            request_id=request_id
        )

        later_than_str = args.get("later_than")
        if later_than_str:
            try:
                later_than = datetime.datetime.fromisoformat(later_than_str)
            except (AttributeError, ValueError):
                return {
                    "message": (
                        f"later_than value {later_than_str} "
                        "is not an ISO 8601 compliant datetime"
                    )
                }, 400
            transform_result_query = transform_result_query.filter(
                TransformationResult.created_at > later_than
            )

        results = [
            transformation_result.to_json(transformation_result)
            for transformation_result in transform_result_query
        ]

        return {"results": results}
