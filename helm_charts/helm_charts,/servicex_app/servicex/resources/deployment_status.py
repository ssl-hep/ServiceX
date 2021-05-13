from flask import jsonify

from servicex.decorators import auth_required
from servicex.resources.servicex_resource import ServiceXResource
from servicex.resources.transform_start import TransformStart
from servicex.transformer_manager import TransformerManager


class DeploymentStatus(ServiceXResource):
    @auth_required
    def get(self, request_id):
        """
        Returns information about the transformer deployment for a given request.
        :param request_id: UUID of transformation request.
        """
        # todo - improve dependency injection
        manager: TransformerManager = TransformStart.transformer_manager
        status = manager.get_deployment_status(request_id)
        if status is None:
            msg = f"Deployment not found for request with id: '{request_id}'"
            return {'message': msg}, 404
        return jsonify(status.to_dict())
