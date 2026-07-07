from sqlalchemy import Select, desc, select

from servicex_app.models import TransformRequest, UserModel
from servicex_app.web.admin.reports import SqlCsvReportView


class UsageReportView(SqlCsvReportView):
    max_download_size = 200 * 1024
    report_name = "Usage"
    endpoint = "usage-report"
    filename = "usage_report.csv"
    description = (
        "List of transforms executed"
    )

    def get_query(self) -> Select:
        return (
            select(
                UserModel.name.label("Name"),
                UserModel.email.label("Email"),
                UserModel.institution.label("Institution"),
                UserModel.created_at.label("Run Time"),
            )
            .join(TransformRequest, TransformRequest.submitted_by == UserModel.id)
            .order_by(desc(UserModel.created_at))
        )
