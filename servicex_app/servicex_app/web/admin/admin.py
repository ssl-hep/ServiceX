import io

import click
from flask import url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.validators import Unique
from flask_admin.form.validators import FieldListInputRequired

from servicex_app.models import UserModel, db
from servicex_app.web.admin import AdminAuthMixin
from servicex_app.web.admin.reports import ReportView
from servicex_app.web.admin.reports.user_transformations import (
    UsersMonthlyReportView,
)  # noqa: F401

Unique.field_flags = {"unique": True}
FieldListInputRequired.field_flags = {"required": True}


class SecureAdminIndexView(AdminAuthMixin, AdminIndexView):
    @expose("/")
    def index(self):
        model_views, other_views = [], []
        for view in self.admin._views:
            if view is self:
                continue
            try:
                list_url = url_for(f"{view.endpoint}.{view._default_view}")
                entry = {"name": view.name, "url": list_url, "endpoint": view.endpoint}
                (model_views if isinstance(view, ModelView) else other_views).append(
                    entry
                )
            except Exception:
                pass
        return self.render(
            "admin/index.html", model_views=model_views, other_views=other_views
        )


class UserModelView(AdminAuthMixin, ModelView):
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


def _all_report_subclasses(cls):
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _all_report_subclasses(subclass)


def init_admin(app):
    admin = Admin(
        app,
        name="ServiceX Admin",
        index_view=SecureAdminIndexView(),
    )
    admin.add_view(UserModelView(UserModel, db.session, name="Users"))
    admin.add_view(
        UsersMonthlyReportView(
            name="Users Monthly Report", endpoint="usersmonthlyreport"
        )
    )

    reports_group = click.Group("reports")
    app.cli.add_command(reports_group)
    for _cls in _all_report_subclasses(ReportView):
        if _cls.report_name:

            @reports_group.command(_cls.report_name, params=_cls.params)
            def cmd(cls=_cls, **kwargs):
                try:
                    output = io.StringIO()
                    cls.write_output(output, **kwargs)
                    click.echo(output.getvalue())
                except Exception as e:
                    raise click.ClickException(str(e)) from e

    return admin
