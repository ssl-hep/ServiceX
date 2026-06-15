from flask import current_app
from flask_jwt_extended import create_refresh_token
from servicex_app.models import UserModel


def check_user_exists(sub):
    return UserModel.find_by_sub(sub)


def add_user(sub, email, name, institution, refresh_token):
    if not refresh_token:
        refresh_token = create_refresh_token(identity=email)

    new_user = UserModel(
        sub=sub,
        email=email,
        name=name,
        institution=institution,
        refresh_token=refresh_token,
        pending=False,
    )

    if new_user.email == current_app.config.get("JWT_ADMIN"):
        new_user.admin = True

    try:
        if not check_user_exists(new_user.sub):
            new_user.save_to_db()
    except Exception as ex:
        print(str(ex))


def list_users(email_filter=None) -> None:
    users = UserModel.query.all()
    if email_filter:
        users = UserModel.query.filter(UserModel.email.ilike(f"%{email_filter}%"))

    print("Sub, Email, Name, Institution, Admin, Pending?")
    for user in users:
        print(
            ", ".join(
                [
                    user.sub,
                    user.email,
                    user.name,
                    user.institution,
                    str(user.admin),
                    "Pending" if user.pending else "Approved",
                ]
            )
        )


def approve_user(email: str) -> None:
    user = UserModel.find_by_email(email)
    if user and user.pending:
        user.pending = False
        user.save_to_db()
        print(f"User {email} approved")
    elif user and not user.pending:
        print(f"User {email} already approved")
    else:
        print(f"User {email} not found")


def set_user_admin(email: str, value: bool = True) -> None:
    user = UserModel.find_by_email(email)
    if not user:
        print(f"User {email} not found")
        return

    if user.admin == value:
        if user.admin:
            print(f"User {email} already admin")
        else:
            print(f"User {email} already not admin")
        return

    user.admin = value
    user.save_to_db()
    if user.admin:
        print(f"User {email} made admin")
        print()
        print(
            f"Please instruct the user to log out and log back in for these changes to take effect!"
        )
    else:
        print(f"User {email} admin privileges revoked")
