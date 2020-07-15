import traceback

import sys
from flask_jwt_extended import (jwt_optional)
from flask_restful import reqparse

from servicex.resources.servicex_resource import ServiceXResource
from servicex.models import UserModel

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)


class DeleteUser(ServiceXResource):
    @jwt_optional
    def post(self):
        is_auth, auth_reject_message = self._validate_user_is_admin()
        if not is_auth:
            return {'message': f'Authentication Failed: {str(auth_reject_message)}'}, 401

        try:
            data = parser.parse_args()
            user: UserModel = UserModel.find_by_username(data['username'])

            if not user:
                return {'message': 'user {} not found'.format(data['username'])}
            else:
                user.delete_from_db()
                return {'message': 'user {} has been deleted'.format(data['username'])}
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': str(exc_value)}, 500
