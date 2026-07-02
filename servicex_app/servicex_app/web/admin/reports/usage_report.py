from datetime import datetime, timedelta

import click
from sqlalchemy import Select, desc, select

from servicex_app.models import TransformRequest, UserModel
from servicex_app.web.admin.reports import SqlCsvReportView


class UsageReportView(SqlCsvReportView):
    report_name = "Usage"
    endpoint = "usage-report"
    filename = "usage_report.csv"
    description = (
        "CSV of all users who have submitted at least one transform in the last N days."
    )
    params = [
        click.Option(
            ["--days"], default=30, type=int, help="Number of days to look back"
        ),
    ]

    def get_query(self, days: int = 30) -> Select:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            select(
                UserModel.name.label("Name"),
                UserModel.email.label("Email"),
                UserModel.institution.label("Institution"),
                UserModel.created_at.label("Run Time"),
            )
            .join(TransformRequest, TransformRequest.submitted_by == UserModel.id)
            .filter(TransformRequest.submit_time >= cutoff)
            .order_by(desc(UserModel.created_at))
        )
