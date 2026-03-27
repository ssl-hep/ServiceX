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
from servicex_app.web.admin.reports.user_transformation_count import (  # noqa: F401
    UserTransformationCountReportView,
)

Unique.field_flags = {"unique": True}
FieldListInputRequired.field_flags = {"required": True}


class AdminModelView(ModelView):
    extra_css = ["/static/admin.css"]
    model_name: str | None = None
    description: str | None = None


class SecureAdminIndexView(AdminAuthMixin, AdminIndexView):
    report_views = []

    @expose("/")
    def index(self):
        model_views, _report_views = [], []
        for view in self.admin._views:
            if view is self:
                continue
            list_url = url_for(f"{view.endpoint}.{view._default_view}")
            entry = {
                "name": view.endpoint,
                "url": list_url,
                "description": view.endpoint
            }

            if isinstance(view, ModelView):
                entry["name"] = view.model.__name__

            if isinstance(view, AdminModelView):
                entry["name"] = view.model_name
                entry["description"] = view.description

            model_views.append(entry)

        for view in self.report_views:
            if view is self or not isinstance(view, ReportView):
                continue
            url = url_for(f"{view.endpoint}.{view._default_view}")
            entry = {
                "name": view.report_name,
                "url": url,
                "description": view.description
            }
            if isinstance(view, ReportView):
                _report_views.append(entry)

        return self.render(
            "admin/index.html",
            model_views=model_views,
            report_views=_report_views,
        )


class UserModelView(AdminAuthMixin, AdminModelView):
    model_name = 'User'
    description = 'ServiceX users'
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


def all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from all_subclasses(sub)


def init_admin(app):
    report_admin = Admin(
        app,
        name="ServiceX Reports",
        url="/report",
        endpoint="report",
    )

    admin_index = SecureAdminIndexView(endpoint="admin")
    admin_index.report_views = report_admin._views
    admin = Admin(
        app,
        name="ServiceX Admin",
        index_view=admin_index,
    )
    admin.add_view(UserModelView(UserModel, db.session, name="Users"))

    reports_group = click.Group("reports")
    app.cli.add_command(reports_group)

    for _cls in all_subclasses(ReportView):
        if _cls.abstract:
            continue

        report_admin.add_view(_cls())

        @reports_group.command(_cls.endpoint, params=_cls.params)
        def cmd(cls=_cls, **kwargs):
            try:
                output = io.StringIO()
                cls().write_output(output, **kwargs)
                click.echo(output.getvalue())
            except Exception as e:
                raise click.ClickException(str(e)) from e

    return admin, report_admin
