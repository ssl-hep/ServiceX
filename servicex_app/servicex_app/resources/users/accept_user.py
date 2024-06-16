from flask_restful import reqparse
from sqlalchemy.orm.exc import NoResultFound

from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.decorators import admin_required
from servicex_app.models import UserModel

parser = reqparse.RequestParser()
parser.add_argument('email', help='This field cannot be blank', required=True)


class AcceptUser(ServiceXResource):
    @admin_required
    def post(self):
        data = parser.parse_args()
        email = data['email']
        try:
            UserModel.accept(email)
            return {'message': 'user {} now ready for access'.format(email)}
        except NoResultFound as err:
            return {'message': str(err)}, 404
