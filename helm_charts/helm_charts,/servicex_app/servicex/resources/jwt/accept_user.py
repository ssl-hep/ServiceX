import sys
import traceback

from flask_restful import Resource, reqparse
from flask_jwt_extended import (create_access_token, create_refresh_token)
from flask_jwt_extended import (jwt_required, get_jwt_identity)
from servicex.models import UserModel

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)


class AcceptUser(Resource):
    @jwt_required
    def post(self):
        user_id = get_jwt_identity()

        try:
            ad = UserModel.find_by_username(user_id).admin
            if not ad:
                return {"message": "Forbidden"}, 403

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
