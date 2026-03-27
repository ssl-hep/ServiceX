from datetime import datetime, timedelta

import click
from sqlalchemy import Select, func, select

from servicex_app.models import TransformRequest, UserModel
from servicex_app.web.admin.reports import SqlCsvReportView


class UserTransformationCountReportView(SqlCsvReportView):
    name = "User Transformation Count"
    endpoint = "user-transformation-count"
    filename = "user_transformation_count.csv"
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
                UserModel.experiment.label("Experiment"),
                func.count(TransformRequest.id).label(f"Transforms (Last {days} Days)"),
            )
            .join(TransformRequest, TransformRequest.submitted_by == UserModel.id)
            .filter(TransformRequest.submit_time >= cutoff)
            .group_by(UserModel.id)
        )
