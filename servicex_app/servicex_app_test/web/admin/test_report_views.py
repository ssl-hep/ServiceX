import csv
import io
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Select

from servicex_app.web.admin.reports import SqlCsvReportView, ReportView
from servicex_app.web.admin.reports.user_transformation_count import (
    UserTransformationCountReportView,
)
from servicex_app_test.web.web_test_base import WebTestBase
from servicex_app.web.admin.admin import all_subclasses


def _mock_result(keys, rows):
    """Build a mock SQLAlchemy CursorResult with .keys() and iteration."""
    result = MagicMock()
    result.keys.return_value = keys
    result.__iter__ = MagicMock(return_value=iter(rows))
    return result


class TestSqlCsvReportView:
    @pytest.fixture
    def mock_db_execute(self, mocker):
        def _setup(keys, rows):
            result = _mock_result(keys, rows)
            mock_db = mocker.patch("servicex_app.models.db")
            mock_db.session.execute.return_value = result
            return result

        return _setup

    def test_write_output_delegates_to_get_query(self, mocker, mock_db_execute):
        mock_db_execute([], [])
        mocker.patch.object(SqlCsvReportView, "get_query", return_value=MagicMock())
        SqlCsvReportView().write_output(io.StringIO())
        SqlCsvReportView.get_query.assert_called_once()

    def test_write_output_passes_kwargs_to_get_query(self, mocker, mock_db_execute):
        mock_db_execute([], [])
        mocker.patch.object(SqlCsvReportView, "get_query", return_value=MagicMock())
        SqlCsvReportView().write_output(io.StringIO(), days=60)
        _, kwargs = SqlCsvReportView.get_query.call_args
        assert kwargs == {"days": 60}

    def test_write_output_uses_result_keys_as_header(self, mock_db_execute):
        mock_db_execute(["col_a", "col_b"], [("val_1", "val_2")])
        output = io.StringIO()

        class ConcreteView(SqlCsvReportView):
            def get_query(self, **kwargs):
                return MagicMock()

        ConcreteView().write_output(output)
        output.seek(0)
        rows = list(csv.reader(output))
        assert rows[0] == ["col_a", "col_b"]
        assert rows[1] == ["val_1", "val_2"]


class TestUserTransformationCountReportView:
    @pytest.fixture
    def mock_db_execute(self, mocker):
        def _setup(keys, rows):
            result = _mock_result(keys, rows)
            mock_db = mocker.patch("servicex_app.models.db")
            mock_db.session.execute.return_value = result
            return result

        return _setup

    def test_get_query_returns_select(self):
        query = UserTransformationCountReportView().get_query(days=30)
        assert isinstance(query, Select)

    def test_get_query_column_labels(self):
        query = UserTransformationCountReportView().get_query(days=30)
        keys = list(query.exported_columns.keys())
        assert keys == [
            "Name",
            "Email",
            "Institution",
            "Experiment",
            "Transforms (Last 30 Days)",
        ]

    def test_get_query_label_reflects_days_parameter(self):
        query = UserTransformationCountReportView().get_query(days=60)
        keys = list(query.exported_columns.keys())
        assert keys[-1] == "Transforms (Last 60 Days)"

    def test_write_output_produces_valid_csv(self, mock_db_execute):
        mock_db_execute(
            ["Name", "Email", "Institution", "Experiment", "Transforms (Last 30 Days)"],
            [("Jane Doe", "jane@example.com", "UChicago", "ATLAS", 5)],
        )
        output = io.StringIO()
        UserTransformationCountReportView().write_output(output, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert rows[0] == [
            "Name",
            "Email",
            "Institution",
            "Experiment",
            "Transforms (Last 30 Days)",
        ]
        assert rows[1] == ["Jane Doe", "jane@example.com", "UChicago", "ATLAS", "5"]

    def test_write_output_empty_result_has_only_header(self, mock_db_execute):
        mock_db_execute(
            ["Name", "Email", "Institution", "Experiment", "Transforms (Last 30 Days)"],
            [],
        )
        output = io.StringIO()
        UserTransformationCountReportView().write_output(output, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert len(rows) == 1


class TestReportViewHttp(WebTestBase):
    @pytest.fixture
    def admin_client(self):
        client = self._test_client(extra_config={"ENABLE_AUTH": True})
        with client.session_transaction() as sess:
            sess["is_authenticated"] = True
            sess["admin"] = True
        return client

    def test_report_index_renders_for_admin(self, admin_client):
        response = admin_client.get("/report/usertransformationcount/")
        assert response.status_code == 200

    def test_generate_download_returns_csv(self, admin_client, mocker):
        mock_db = mocker.patch("servicex_app.models.db")
        mock_db.session.execute.return_value = _mock_result(["Name"], [])
        response = admin_client.post(
            "/report/usertransformationcount/generate",
            data={"days": "30"},
        )
        assert response.status_code == 200
        assert "text/csv" in response.content_type
        assert "attachment" in response.headers.get("Content-Disposition", "")


class TestAllReportSubclasses:
    def test_includes_direct_subclass(self):
        subclasses = all_subclasses(ReportView)
        assert SqlCsvReportView in subclasses

    def test_includes_indirect_subclass(self):
        subclasses = all_subclasses(ReportView)
        assert UserTransformationCountReportView in subclasses

    def test_empty_for_leaf_class(self):
        subclasses = all_subclasses(ReportView)
        assert subclasses == []

    def test_includes_grandchild_via_sql_csv_report_view(self):
        csv_subclasses = all_subclasses(SqlCsvReportView)
        assert UserTransformationCountReportView in csv_subclasses
