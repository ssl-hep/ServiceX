from unittest.mock import MagicMock

import pytest

from servicex_app.cli.user_commands import list_users


def _make_user(
    sub="sub1",
    email="user@example.com",
    name="Test User",
    institution="UChicago",
    admin=False,
    pending=False,
):
    user = MagicMock()
    user.sub = sub
    user.email = email
    user.name = name
    user.institution = institution
    user.admin = admin
    user.pending = pending
    return user


class TestListUsers:
    def test_header_includes_admin_column(self, mocker, capsys):
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = []
        list_users()
        assert "Admin" in capsys.readouterr().out

    def test_prints_admin_true_for_admin_user(self, mocker, capsys):
        user = _make_user(admin=True)
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = [user]
        list_users()
        assert "True" in capsys.readouterr().out

    def test_prints_admin_false_for_non_admin_user(self, mocker, capsys):
        user = _make_user(admin=False)
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = [user]
        list_users()
        assert "False" in capsys.readouterr().out

    def test_prints_pending_status(self, mocker, capsys):
        user = _make_user(pending=True)
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = [user]
        list_users()
        assert "Pending" in capsys.readouterr().out

    def test_prints_approved_status(self, mocker, capsys):
        user = _make_user(pending=False)
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = [user]
        list_users()
        assert "Approved" in capsys.readouterr().out

    def test_lists_all_users_without_filter(self, mocker, capsys):
        user1 = _make_user(sub="a", email="a@x.com")
        user2 = _make_user(sub="b", email="b@x.com")
        mocker.patch(
            "servicex_app.cli.user_commands.UserModel"
        ).query.all.return_value = [user1, user2]
        list_users()
        out = capsys.readouterr().out
        assert "a@x.com" in out
        assert "b@x.com" in out

    def test_with_email_filter_calls_ilike_query(self, mocker, capsys):
        mock_model = mocker.patch("servicex_app.cli.user_commands.UserModel")
        mock_model.query.all.return_value = []
        mock_model.query.filter.return_value = iter([])
        list_users(email_filter="@cern.ch")
        mock_model.query.filter.assert_called_once()

    def test_without_filter_does_not_call_filter(self, mocker, capsys):
        mock_model = mocker.patch("servicex_app.cli.user_commands.UserModel")
        mock_model.query.all.return_value = []
        list_users()
        mock_model.query.filter.assert_not_called()
