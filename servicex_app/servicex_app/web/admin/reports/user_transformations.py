import csv
from datetime import datetime, timedelta

import click
from sqlalchemy import func

from servicex_app.models import TransformRequest, UserModel, db
from servicex_app.web.admin.reports import CsvReportView


class UsersTransformationCountReportView(CsvReportView):
    report_name = "users-transformations-count"
    filename = "users_transformation_count.csv"
    description = (
        "CSV of all users who have submitted at least one transform in the last N days."
    )
    params = [
        click.Option(
            ["--days"], default=30, type=int, help="Number of days to look back"
        ),
    ]

    @classmethod
    def write_csv(cls, writer: csv.writer, days: int = 30) -> csv:
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
