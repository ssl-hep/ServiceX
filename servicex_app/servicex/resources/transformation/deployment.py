from flask import jsonify, current_app

from servicex.decorators import auth_required
from servicex.resources.servicex_resource import ServiceXResource
from servicex.transformer_manager import TransformerManager


class DeploymentStatus(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager: TransformerManager):
        cls.transformer_manager = transformer_manager

    @auth_required
    def get(self, request_id):
        """
        Returns information about the transformer deployment for a given request.
        :param request_id: UUID of transformation request.
        """
        status = self.transformer_manager.get_deployment_status(request_id)
        if status is None:
            msg = f"Deployment not found: '{request_id}'"
            current_app.logger.error(msg, extra={'requestId': request_id})
            return {'message': msg}, 404
        current_app.logger.debug(f"Transformation deployment request: {status.to_dict()}")
        return jsonify(status.to_dict())
