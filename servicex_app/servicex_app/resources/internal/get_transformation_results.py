import logging

from datetime import datetime
from flask_restful import reqparse

from servicex_app.decorators import auth_required
from servicex_app.models import TransformationResult
from servicex_app.resources.servicex_resource import ServiceXResource

logger = logging.getLogger(__name__)


class GetTransformationResults(ServiceXResource):
    @auth_required
    def get(self, request_id):
        if not request_id:
            return {"message": "Missing required transformation request_id"}, 400

        transform_result_query = TransformationResult.query.filter_by(request_id=request_id).all()
        results = [transformation_result.to_json(transformation_result) for transformation_result in transform_result_query]

        return {
            "results": results
        }
