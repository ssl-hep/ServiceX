from servicex.models import UserModel


def accept_user(username):
    pending_user = UserModel.find_by_username(username)
    if not pending_user:
        return {'message': 'user {} not registered'.format(username)}
    else:
        pending_user.pending = False
        pending_user.save_to_db()
        return {'message': 'user {} now ready for access'.format(username)}
