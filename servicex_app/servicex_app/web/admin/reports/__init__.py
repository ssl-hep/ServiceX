import csv
import io
from typing import TextIO

from flask import Response, request, url_for
from flask_admin import BaseView, expose

from servicex_app.web.admin import AdminAuthMixin


class ReportView(AdminAuthMixin, BaseView):
    report_name = None
    template = "admin/report.html"
    description = None
    filename = "report.txt"
    mimetype = "application/octet-stream"
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


class CsvReportView(ReportView):
    filename = "report.csv"
    mimetype = "text/csv"

    @classmethod
    def write_csv(cls, writer: csv.writer, **kwargs) -> None:
        raise NotImplementedError

    @classmethod
    def write_output(cls, output: TextIO, **kwargs) -> None:
        writer = csv.writer(output)
        cls.write_csv(writer, **kwargs)
