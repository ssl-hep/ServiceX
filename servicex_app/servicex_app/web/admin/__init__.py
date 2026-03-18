from flask import current_app, redirect, request, session, url_for
from flask_admin import expose
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from servicex_app.decorators import get_jwt_user


class AdminAuthMixin:
    def is_accessible(self):
        return self._is_admin()

    def inaccessible_callback(self, name, **kwargs):
        session["next"] = request.url
        return redirect(url_for("sign_in"))

    def _is_admin(self):
        if not current_app.config.get("ENABLE_AUTH"):
            return False
        if session.get("is_authenticated") and session.get("admin"):
            return True
        try:
            verify_jwt_in_request(locations=["headers"])
            user = get_jwt_user()
            return user is not None and user.admin
        except (NoAuthorizationError, Exception):
            return False


from servicex_app.web.admin.admin import init_admin  # noqa: E402

__all__ = ["AdminAuthMixin", "init_admin"]
