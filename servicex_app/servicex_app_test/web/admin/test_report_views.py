import csv
import io
from unittest.mock import MagicMock

import pytest

from servicex_app.web.admin.admin import _all_report_subclasses
from servicex_app.web.admin.reports import CsvReportView, ReportView
from servicex_app.web.admin.reports.user_transformations import UsersMonthlyReportView


class TestCsvReportView:
    def test_write_output_delegates_to_write_csv(self, mocker):
        mock_write_csv = mocker.patch.object(CsvReportView, "write_csv")
        output = io.StringIO()
        CsvReportView.write_output(output)
        mock_write_csv.assert_called_once()

    def test_write_output_passes_kwargs_to_write_csv(self, mocker):
        mock_write_csv = mocker.patch.object(CsvReportView, "write_csv")
        output = io.StringIO()
        CsvReportView.write_output(output, days=60)
        _, kwargs = mock_write_csv.call_args
        assert kwargs == {"days": 60}

    def test_write_output_produces_valid_csv(self, mocker):
        def fake_write_csv(writer, **kwargs):
            writer.writerow(["col_a", "col_b"])
            writer.writerow(["val_1", "val_2"])

        mocker.patch.object(CsvReportView, "write_csv", side_effect=fake_write_csv)
        output = io.StringIO()
        CsvReportView.write_output(output)
        output.seek(0)
        rows = list(csv.reader(output))
        assert rows[0] == ["col_a", "col_b"]
        assert rows[1] == ["val_1", "val_2"]


class TestUsersMonthlyReportView:
    @pytest.fixture
    def mock_db_query(self, mocker):
        def _setup(results):
            mock_chain = MagicMock()
            mock_chain.join.return_value = mock_chain
            mock_chain.filter.return_value = mock_chain
            mock_chain.group_by.return_value = mock_chain
            mock_chain.all.return_value = results
            mocker.patch(
                "servicex_app.web.admin.reports.user_transformations.db.session.query",
                return_value=mock_chain,
            )
            return mock_chain

        return _setup

    def _make_mock_user(self, name="Jane Doe", email="jane@example.com",
                        institution="UChicago", experiment="ATLAS"):
        user = MagicMock()
        user.name = name
        user.email = email
        user.institution = institution
        user.experiment = experiment
        return user

    def test_write_csv_outputs_header_row(self, mock_db_query):
        mock_db_query([])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert rows[0] == [
            "Name", "Email", "Institution", "Experiment",
            "Transforms (Last 30 Days)",
        ]

    def test_write_csv_header_reflects_days_parameter(self, mock_db_query):
        mock_db_query([])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer, days=60)
        output.seek(0)
        rows = list(csv.reader(output))
        assert "60 Days" in rows[0][-1]

    def test_write_csv_default_days_is_30(self, mock_db_query):
        mock_db_query([])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer)
        output.seek(0)
        rows = list(csv.reader(output))
        assert "30 Days" in rows[0][-1]

    def test_write_csv_outputs_user_rows(self, mock_db_query):
        user = self._make_mock_user()
        mock_db_query([(user, 5)])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert rows[1] == ["Jane Doe", "jane@example.com", "UChicago", "ATLAS", "5"]

    def test_write_csv_outputs_multiple_user_rows(self, mock_db_query):
        user1 = self._make_mock_user(name="Alice", email="alice@example.com")
        user2 = self._make_mock_user(name="Bob", email="bob@example.com")
        mock_db_query([(user1, 3), (user2, 7)])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert len(rows) == 3  # header + 2 users
        assert rows[1][0] == "Alice"
        assert rows[2][0] == "Bob"

    def test_write_csv_empty_result_has_only_header(self, mock_db_query):
        mock_db_query([])
        output = io.StringIO()
        writer = csv.writer(output)
        UsersMonthlyReportView.write_csv(writer, days=30)
        output.seek(0)
        rows = list(csv.reader(output))
        assert len(rows) == 1


class TestAllReportSubclasses:
    def test_includes_direct_subclass(self):
        subclasses = list(_all_report_subclasses(ReportView))
        assert CsvReportView in subclasses

    def test_includes_indirect_subclass(self):
        subclasses = list(_all_report_subclasses(ReportView))
        assert UsersMonthlyReportView in subclasses

    def test_empty_for_leaf_class(self):
        subclasses = list(_all_report_subclasses(UsersMonthlyReportView))
        assert subclasses == []

    def test_includes_grandchild_via_csv_report_view(self):
        csv_subclasses = list(_all_report_subclasses(CsvReportView))
        assert UsersMonthlyReportView in csv_subclasses
