import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, Text
from sqlalchemy.dialects.postgresql import ENUM

from servicex_orchestrator import models
from servicex_orchestrator.activities.stubs import lookup_workflow_id
from servicex_orchestrator.config import Settings
from servicex_orchestrator.db import (
    DatabaseUnavailable,
    SchemaMismatch,
    create_engine,
    startup_check,
    tables,
)
from servicex_orchestrator.db.engine import async_url
from servicex_orchestrator.db.schema_check import DbColumn, compare
from servicex_orchestrator.worker import open_database


def test_database_settings():
    settings = Settings.from_env(
        {
            "DATABASE_URL": "postgresql://orch:secret@db:5432/servicex",
            "DB_POOL_SIZE": "3",
            "DB_MAX_OVERFLOW": "0",
        }
    )
    assert settings.database_url == "postgresql://orch:secret@db:5432/servicex"
    assert (settings.db_pool_size, settings.db_max_overflow) == (3, 0)
    assert "secret" not in repr(settings)
    defaults = Settings.from_env({})
    assert defaults.database_url is None
    assert (defaults.db_pool_size, defaults.db_max_overflow) == (5, 5)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@h/d",
        "postgresql+psycopg2://u:p@h/d",
        "postgresql+asyncpg://u:p@h/d",
    ],
)
def test_async_url_forces_asyncpg(url):
    assert async_url(url).drivername == "postgresql+asyncpg"
    assert async_url(url).password == "p"


def test_async_url_rejects_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        async_url("sqlite:////sqlite/app.db")


def test_lookup_workflow_is_keyed_on_the_dataset_row():
    assert lookup_workflow_id(42) == "dataset-42"


def test_lookup_statuses_fit_the_column():
    statuses = [
        models.LOOKUP_COMPLETE,
        models.LOOKUP_DOES_NOT_EXIST,
        models.LOOKUP_BAD_NAME,
        models.LOOKUP_INTERNAL_FAILURE,
        "looking",
    ]
    length = tables.datasets.c.lookup_status.type.length
    assert max(len(s) for s in statuses) <= length


def test_request_statuses_are_enum_labels():
    labels = set(tables.TRANSFORM_STATUS.enums)
    for status in (
        models.REQUEST_COMPLETE,
        models.REQUEST_FATAL,
        models.REQUEST_BAD_DATASET,
        models.REQUEST_CANCELED,
    ):
        assert status in labels


# ----- compare() on a small schema ----------------------------------------------

STATUS = ENUM("a", "b", name="status", create_type=False)


def _metadata():
    md = MetaData()
    Table(
        "things",
        md,
        Column("id", Integer, primary_key=True),
        Column("name", String(10), nullable=False),
        Column("note", Text, nullable=True, info=tables.WRITES),
        Column("status", STATUS, nullable=True, info=tables.WRITES),
    )
    Table("log", md, Column("id", Integer, primary_key=True), info=tables.WRITES)
    return md


def _col(table, name, type_, not_null=False, select=True, update=False, insert=False):
    return DbColumn(table, name, type_, not_null, select, update, insert)


def _good():
    return [
        _col("things", "id", "integer", not_null=True),
        _col("things", "name", "character varying(10)", not_null=True),
        _col("things", "note", "text", update=True),
        _col("things", "status", "status", update=True),
        _col("things", "extra", "text"),  # app-only columns are ignored
        _col("log", "id", "integer", not_null=True, update=True, insert=True),
    ]


def _replace(columns, table, name, **changes):
    out = []
    for c in columns:
        if (c.table, c.name) == (table, name):
            fields = {**c.__dict__, **changes}
            c = DbColumn(**fields)
        out.append(c)
    return out


def test_compare_accepts_matching_schema():
    assert compare(_good(), {"status": {"a", "b", "c"}}, _metadata()) == []


def test_compare_accepts_longer_and_unbounded_varchar():
    for db_type in ("character varying(20)", "character varying"):
        columns = _replace(_good(), "things", "name", type=db_type)
        assert compare(columns, {"status": {"a", "b"}}, _metadata()) == []


@pytest.mark.parametrize(
    "change, expected",
    [
        (dict(table="things", name="note", remove=True), "things.note is missing"),
        (
            dict(table="things", name="name", type="character varying(5)"),
            "things.name is character varying(5), too short",
        ),
        (dict(table="things", name="note", type="bigint"), "expected text"),
        (dict(table="things", name="note", not_null=True), "NOT NULL in the database"),
        (dict(table="things", name="name", not_null=False), "nullable in the database"),
        (dict(table="things", name="name", can_select=False), "no SELECT"),
        (dict(table="things", name="note", can_update=False), "no UPDATE"),
        (dict(table="log", name="id", can_insert=False), "log: no INSERT"),
    ],
)
def test_compare_reports(change, expected):
    table, name = change.pop("table"), change.pop("name")
    columns = _good()
    if change.pop("remove", False):
        columns = [c for c in columns if (c.table, c.name) != (table, name)]
    else:
        columns = _replace(columns, table, name, **change)
    problems = compare(columns, {"status": {"a", "b"}}, _metadata())
    assert len(problems) == 1 and expected in problems[0], problems


def test_compare_reports_missing_enum_label_and_table():
    columns = [c for c in _good() if c.table != "log"]
    problems = compare(columns, {"status": {"a"}}, _metadata())
    assert problems == ["things.status: enum status lacks b", "table log is missing"]


def test_schema_mismatch_message_names_revisions():
    err = SchemaMismatch("v1_9_0", ["requests.workflow_id is missing"])
    assert "alembic revision v1_9_0" in str(err)
    assert tables.REQUIRED_SCHEMA_REVISION in str(err)
    assert "requests.workflow_id is missing" in str(err)


# ----- startup ------------------------------------------------------------------


async def test_startup_check_reports_unreachable_database():
    # Port 1 on localhost refuses connections immediately.
    settings = Settings.from_env(
        {"DATABASE_URL": "postgresql://orch:hunter2@127.0.0.1:1/servicex"}
    )
    engine = create_engine(settings)
    try:
        with pytest.raises(DatabaseUnavailable) as err:
            await startup_check(engine)
    finally:
        await engine.dispose()
    assert "orch@127.0.0.1:1/servicex" in str(err.value)
    assert "hunter2" not in str(err.value)


async def test_open_database_requires_url():
    with pytest.raises(DatabaseUnavailable, match="DATABASE_URL is not set"):
        await open_database(Settings.from_env({}))
