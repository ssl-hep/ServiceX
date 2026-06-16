from flask import redirect, url_for, session

from servicex_app.models import UserModel


class AdminAuthMixin:
    endpoint: str | None = None

    def is_accessible(self):
        email = session.get("email")

        if email is None:
            return False

        user = UserModel.find_by_email(email)

        if user is None:
            return False

        return user.admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("home"))


from servicex_app.web.admin.admin import init_admin  # noqa: E402

__all__ = ["AdminAuthMixin", "init_admin"]
