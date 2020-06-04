import sys
import traceback

from flask_restful import Resource, reqparse
from flask_jwt_extended import (create_access_token, create_refresh_token)
from flask_jwt_extended import (jwt_required, get_jwt_identity)
from servicex.models import UserModel, PendingUserModel

parser = reqparse.RequestParser()
parser.add_argument('username', help='This field cannot be blank', required=True)


class AcceptUser(Resource):
    @jwt_required
    def post(self):
        user_id = get_jwt_identity()
        ad = UserModel.find_by_username(user_id).admin
        if ad == 0:
            return {"message": "Forbidden"}, 403

        data = parser.parse_args()

        if not PendingUserModel.find_by_username(data['username']):
            return {'message': 'user {} not registered'.format(data['username'])}

        new_user = UserModel(
            username=data['username'],
            key=PendingUserModel.find_by_username(data['username']).key,
            admin=0
        )

        try:
            new_user.save_to_db()
            PendingUserModel.delete_one(data['username'])
            access_token = create_access_token(identity=data['username'])
            refresh_token = create_refresh_token(identity=data['username'])
            return {
                'message': 'User {} was created'.format(data['username']),
                'access_token': access_token,
                'refresh_token': refresh_token
                }
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=20, file=sys.stdout)
            print(exc_value)
            return {'message': str(exc_value)}, 500
