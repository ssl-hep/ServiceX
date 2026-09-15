from flask import jsonify, current_app

from servicex_app.decorators import auth_required
from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.transformer_manager import TransformerManager


class DeploymentStatus(ServiceXResource):
    @classmethod
    def make_api(cls, transformer_manager: TransformerManager):
        cls.transformer_manager = transformer_manager

    @auth_required
    def get(self, request_id):
        """
        Returns information about the transformer Job for a given request.
        :param request_id: UUID of transformation request.
        """
        status = self.transformer_manager.get_deployment_status(request_id)
        if status is None:
            msg = f"Transformer Job not found: '{request_id}'"
            current_app.logger.error(msg, extra={"request_id": request_id})
            return {"message": msg}, 404
        current_app.logger.debug(f"Transformer Job status: {status.to_dict()}")
        return jsonify(status.to_dict())
