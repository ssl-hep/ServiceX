from flask import current_app, redirect, url_for

from servicex_app.decorators import is_admin_user


class AdminAuthMixin:
    endpoint: str | None = None

    def is_accessible(self):
        return is_admin_user()

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("home"))


from servicex_app.web.admin.admin import init_admin  # noqa: E402

__all__ = ["AdminAuthMixin", "init_admin"]
