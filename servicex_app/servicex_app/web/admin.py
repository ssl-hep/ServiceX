import csv
import io
from datetime import datetime, timedelta

import click
from flask import Response, current_app, redirect, request, session, url_for
from typing import TextIO
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.validators import Unique
from flask_admin.form.validators import FieldListInputRequired
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError
from sqlalchemy import func

from servicex_app.decorators import get_jwt_user
from servicex_app.models import TransformRequest, UserModel, db

Unique.field_flags = {"unique": True}
FieldListInputRequired.field_flags = {"required": True}


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


class TemplateMixin:
    template = None

    @expose("/")
    def index(self):
        return self.render(self.template)


class ReportView(AdminAuthMixin, TemplateMixin, BaseView):
    report_name = None
    template = "admin/report.html"
    description = None
    params = []

    @classmethod
    def write_output(cls, output: TextIO, **kwargs):
        raise NotImplementedError

    @expose("/")
    def index(self):
        return self.render(
            self.template,
            params=self.params,
            title=self.name,
            description=self.description,
            generate_url=url_for(f"{self.endpoint}.generate_download"),
        )

    @classmethod
    def _get_params_as_kwargs(cls):
        return {
            p.name: p.type.convert(request.form.get(p.name, p.default), p, None)
            for p in cls.params
        }

    @expose("/generate", methods=["POST"])
    def generate_download(self):
        kwargs = self._get_params_as_kwargs()
        output = io.StringIO()
        self.write_output(output, **kwargs)
        return Response(
            output.getvalue(),
            mimetype=self.mimetype,
            headers={"Content-Disposition": f"attachment; filename={self.filename}"},
        )


class CsvReportView(ReportView):
    filename = "report.csv"
    mimetype = "text/csv"

    @classmethod
    def write_csv(cls, writer: csv.writer, **kwargs) -> None:
        raise NotImplementedError

    @classmethod
    def write_output(cls, output: TextIO, **kwargs) -> None:
        kwargs = cls._get_params_as_kwargs()
        writer = csv.writer(output)
        cls.write_csv(writer, **kwargs)


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


class UsersMonthlyReportView(CsvReportView):
    report_name = "users-monthly"
    filename = "users_monthly_report.csv"
    description = (
        "CSV of all users who have submitted at least one transform in the last N days."
    )
    params = [
        click.Option(
            ["--days"], default=30, type=int, help="Number of days to look back"
        ),
    ]

    @classmethod
    def write_csv(cls, writer: csv.writer, days: int = 30) -> None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        results = (
            db.session.query(
                UserModel, func.count(TransformRequest.id).label("transform_count")
            )
            .join(TransformRequest, TransformRequest.submitted_by == UserModel.id)
            .filter(TransformRequest.submit_time >= cutoff)
            .group_by(UserModel.id)
            .all()
        )
        writer.writerow(
            [
                "Name",
                "Email",
                "Institution",
                "Experiment",
                f"Transforms (Last {days} Days)",
            ]
        )
        for user, count in results:
            writer.writerow(
                [user.name, user.email, user.institution, user.experiment, count]
            )


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
    for _cls in ReportView.__subclasses__():
        if _cls.report_name:

            @reports_group.command(_cls.report_name, params=_cls.params)
            def cmd(cls=_cls, **kwargs):
                try:
                    output = io.StringIO()
                    output = cls.write_output(output, **kwargs)
                    click.echo(output.getvalue())
                except Exception as e:
                    raise click.ClickException(str(e)) from e

    return admin
