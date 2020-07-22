from servicex.resources.servicex_resource import ServiceXResource
from servicex.decorators import admin_required
from servicex.models import UserModel


class DeleteUser(ServiceXResource):
    @admin_required
    def delete(self, user_id):
        user: UserModel = UserModel.find_by_id(user_id)
        if not user:
            return {'message': 'user {} not found'.format(user_id)}, 404
        user.delete_from_db()
        return {'message': 'user {} has been deleted'.format(user_id)}, 200
