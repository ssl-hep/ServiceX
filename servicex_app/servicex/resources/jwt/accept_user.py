import traceback

import sys
from flask_jwt_extended import (jwt_optional)
from flask_restful import reqparse

from resources.servicex_resource import ServiceXResource
from servicex.models import UserModel

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)


class AcceptUser(ServiceXResource):
    @jwt_optional
    def post(self):
        is_auth, auth_reject_message = self._validate_user_is_admin()
        if not is_auth:
            return {'message': f'Authentication Failed: {str(auth_reject_message)}'}, 401
        else:
            try:
                data = parser.parse_args()
                pending_user = UserModel.find_by_username(data['username'])

                if not pending_user:
                    return {'message': 'user {} not registered'.format(data['username'])}
                else:
                    pending_user.pending = False
                    pending_user.save_to_db()
                    return {'message': 'user {} now ready for access'.format(data['username'])}

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
                print(exc_value)
                return {'message': str(exc_value)}, 500
