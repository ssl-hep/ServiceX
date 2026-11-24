from unittest.mock import MagicMock

import pytest

from servicex_app import orchestrator_db_role as role


def test_grant_statements_reset_then_grant():
    statements = role.grant_statements("servicex_orchestrator", "servicex")
    r = '"servicex_orchestrator"'
    assert statements[:5] == [
        f'GRANT CONNECT ON DATABASE "servicex" TO {r}',
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"GRANT USAGE ON SCHEMA public TO {r}",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {r}",
    ]
    grants = statements[5:]
    assert (
        'GRANT SELECT, UPDATE ("lookup_status", "n_files", "size", "events", '
        f'"last_updated") ON TABLE datasets TO {r}'
    ) in grants
    assert f"GRANT SELECT ON TABLE files TO {r}" in grants
    assert f"GRANT SELECT, INSERT, UPDATE ON TABLE transform_result TO {r}" in grants
    assert f"GRANT USAGE, SELECT ON SEQUENCE transform_result_id_seq TO {r}" in grants
    requests = [g for g in grants if "ON TABLE requests" in g]
    assert len(requests) == 1
    assert 'UPDATE ("status", "finish_time"' in requests[0]
    assert '"title"' not in requests[0]
    assert not any("DELETE" in g or "TRUNCATE" in g for g in grants)


def test_quotes_database_name():
    statements = role.grant_statements("orch", 'we"ird')
    assert statements[0] == 'GRANT CONNECT ON DATABASE "we""ird" TO "orch"'


def test_role_statements_escape_password():
    create, alter = role.role_statements("orch", "it's%a$$secret")
    assert "rolname = 'orch'" in create
    assert 'CREATE ROLE "orch" LOGIN' in create
    assert alter.endswith("PASSWORD 'it''s%a$$secret'")
    assert "NOSUPERUSER" in alter


@pytest.mark.parametrize("name", ["Orch", "orch; DROP TABLE x", "o-r", ""])
def test_rejects_unsafe_role_names(name):
    with pytest.raises(ValueError):
        role.role_statements(name, "pw")


def test_rejects_nul_in_password():
    with pytest.raises(ValueError):
        role.role_statements("orch", "a\x00b")


def _engine(current_user="postgres", dialect="postgresql"):
    engine = MagicMock()
    engine.dialect.name = dialect
    conn = engine.begin.return_value.__enter__.return_value
    conn.execute.return_value.scalar.side_effect = [current_user, "servicex"]
    return engine, conn


def test_apply_runs_everything_in_one_transaction():
    engine, conn = _engine()
    role.apply(engine, "orch", "pw")
    engine.begin.assert_called_once()
    cursor = conn.connection.cursor.return_value
    executed = [c.args[0] for c in cursor.execute.call_args_list]
    assert all(len(c.args) == 1 for c in cursor.execute.call_args_list)
    cursor.close.assert_called_once()
    assert executed == role.role_statements("orch", "pw") + role.grant_statements(
        "orch", "servicex"
    )
    lock_sql = str(conn.execute.call_args_list[1].args[0])
    assert "pg_advisory_xact_lock" in lock_sql


def test_apply_refuses_own_role():
    engine, _ = _engine(current_user="orch")
    with pytest.raises(ValueError):
        role.apply(engine, "orch", "pw")


def test_apply_refuses_sqlite():
    engine, _ = _engine(dialect="sqlite")
    with pytest.raises(RuntimeError):
        role.apply(engine, "orch", "pw")


def test_apply_needs_password():
    engine, _ = _engine()
    with pytest.raises(ValueError):
        role.apply(engine, "orch", "")
