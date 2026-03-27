import csv
import io
from typing import TextIO

from sqlalchemy import Select
from sqlalchemy.engine import CursorResult

from flask import Response, request, url_for
from flask_admin import BaseView, expose

from servicex_app.web.admin import AdminAuthMixin


class ReportView(AdminAuthMixin, BaseView):
    name = None
    template = "admin/report.html"
    description = None
    filename = "report.txt"
    mimetype = "application/octet-stream"
    params = []
    abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'abstract' not in cls.__dict__:
            cls.abstract = False

    def write_output(self, output: TextIO, **kwargs):
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

    @expose("/generate", methods=["POST"])
    def generate_download(self):
        kwargs = {
            p.name: p.type.convert(request.form.get(p.name, p.default), p, None)
            for p in self.params
        }
        output = io.StringIO()
        self.write_output(output, **kwargs)
        return Response(
            output.getvalue(),
            mimetype=self.mimetype,
            headers={"Content-Disposition": f"attachment; filename={self.filename}"},
        )


class SqlCsvReportView(ReportView):
    filename = "report.csv"
    mimetype = "text/csv"
    abstract = True

    def get_query(self, **kwargs) -> Select:
        raise NotImplementedError

    def write_output(self, output: TextIO, **kwargs) -> None:
        from servicex_app.models import db

        writer = csv.writer(output)
        results: CursorResult = db.session.execute(self.get_query(**kwargs))
        writer.writerow(results.keys())
        for row in results:
            writer.writerow(row)
