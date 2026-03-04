from flask import current_app, redirect, request, session, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.validators import Unique
from flask_admin.form.validators import FieldListInputRequired
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from servicex_app.decorators import get_jwt_user
from servicex_app.models import UserModel, db

# flask-admin 1.6.x validators use tuple field_flags; wtforms 3.x expects dicts.
Unique.field_flags = {"unique": True}
FieldListInputRequired.field_flags = {"required": True}


def _is_admin():
    if not current_app.config.get("ENABLE_AUTH"):
        return True
    if session.get("is_authenticated") and session.get("admin"):
        return True
    try:
        verify_jwt_in_request(locations=["headers"])
        user = get_jwt_user()
        return user is not None and user.admin
    except (NoAuthorizationError, Exception):
        return False


class SecureAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not _is_admin():
            return redirect(url_for("sign_in"))
        users = UserModel.query.order_by(UserModel.created_at.desc()).all()
        return self.render("admin/index.html", users=users)

    def is_accessible(self):
        return _is_admin()

    def inaccessible_callback(self, name, **kwargs):
        session["next"] = request.url
        return redirect(url_for("sign_in"))


class UserModelView(ModelView):
    column_list = [
        "name",
        "email",
        "institution",
        "experiment",
        "admin",
        "pending",
        "created_at",
        "updated_at",
    ]
    column_searchable_list = ["name", "email", "institution"]
    column_filters = ["admin", "pending", "institution", "experiment"]
    column_editable_list = ["admin", "pending"]
    column_default_sort = ("created_at", True)

    form_columns = [
        "name",
        "email",
        "institution",
        "experiment",
        "sub",
        "admin",
        "pending",
    ]

    can_create = False

    def is_accessible(self):
        return _is_admin()

    def inaccessible_callback(self, name, **kwargs):
        session["next"] = request.url
        return redirect(url_for("sign_in"))


def init_admin(app):
    admin = Admin(
        app,
        name="ServiceX Admin",
        index_view=SecureAdminIndexView(),
        template_mode="bootstrap4",
    )
    admin.add_view(UserModelView(UserModel, db.session, name="Users"))
    return admin
