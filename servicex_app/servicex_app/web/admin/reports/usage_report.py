from sqlalchemy import Select, desc, select, cast, String

from servicex_app.models import TransformRequest, UserModel
from servicex_app.web.admin.reports import SqlCsvReportView


class UsageReportView(SqlCsvReportView):
    max_download_size = 200 * 1024
    report_name = "Usage"
    endpoint = "usage-report"
    filename = "usage_report.csv"
    description = "List of transforms executed"

    def get_query(self) -> Select:
        return (
            select(
                UserModel.name.label("Name"),
                UserModel.email.label("Email"),
                UserModel.institution.label("Institution"),
                TransformRequest.title.label("Title"),
                cast(TransformRequest.status, String).label("Status"),
                TransformRequest.submit_time.label("Run Time"),
                TransformRequest.finish_time.label("Finish Time"),
                TransformRequest.did.label("Dataset Identifier (DID)"),
                TransformRequest.image.label("Image"),
                TransformRequest.workers.label("Workers"),
                TransformRequest.result_destination.label("Result Destination"),
                TransformRequest.result_format.label("Result Format"),
                TransformRequest.files.label("File Count"),
                TransformRequest.files_completed.label("Files Completed"),
                TransformRequest.files_failed.label("Files Failed"),
                TransformRequest.total_events.label("Total Events"),
                TransformRequest.did_lookup_time.label("DID Lookup Time"),
                TransformRequest.app_version.label("App Version"),
                TransformRequest.code_gen_image.label("Code Gen Image"),
                TransformRequest.transformer_language.label("Transformer Language"),
                TransformRequest.transformer_command.label("Transformer Command"),
            )
            .join(TransformRequest, TransformRequest.submitted_by == UserModel.id)
            .order_by(desc(TransformRequest.submit_time))
        )
