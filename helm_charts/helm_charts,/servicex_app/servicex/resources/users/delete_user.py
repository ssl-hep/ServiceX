import traceback

import sys
from flask_jwt_extended import (jwt_optional)

from servicex.resources.servicex_resource import ServiceXResource
from servicex.models import UserModel


class DeleteUser(ServiceXResource):
    @jwt_optional
    def delete(self, user_id):
        is_auth, auth_reject_message = self._validate_user_is_admin()
        if not is_auth:
            return {'message': f'Authentication Failed: {str(auth_reject_message)}'}, 401

        try:
            user: UserModel = UserModel.query.get(user_id)
            if not user:
                return {'message': 'user {} not found'.format(user_id)}, 404
            else:
                user.delete_from_db()
                return {'message': 'user {} has been deleted'.format(user_id)}
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': str(exc_value)}, 500
