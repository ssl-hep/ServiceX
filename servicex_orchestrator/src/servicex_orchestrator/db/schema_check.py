"""Check the live database against the orchestrator's tables.

Used at worker startup and by the schema contract test. It reads pg_catalog rather
than information_schema, which hides columns the current role has no privilege on.
"""

import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.asyncio import AsyncConnection

from servicex_orchestrator.db.tables import (
    REQUIRED_SCHEMA_REVISION,
    metadata as orchestrator_metadata,
    writes_column,
    writes_table,
)


@dataclass(frozen=True)
class DbColumn:
    """One column as Postgres reports it, with the current role's privileges."""

    table: str
    name: str
    type: str  # format_type(): "integer", "character varying(48)", "transformstatus"
    not_null: bool
    can_select: bool
    can_update: bool
    can_insert: bool  # on the table


class SchemaMismatch(Exception):
    def __init__(self, revision: Optional[str], problems: list[str]):
        self.revision = revision
        self.problems = problems
        found = f"alembic revision {revision}" if revision else "no alembic revision"
        super().__init__(
            f"The ServiceX database ({found}) does not match what this orchestrator "
            f"expects (app migrations up to at least {REQUIRED_SCHEMA_REVISION}, and "
            "the grants of `flask orchestrator-db-role`). On a fresh install this "
            "clears once the app has migrated the database. Problems:\n  - "
            + "\n  - ".join(problems)
        )


_VARCHAR = re.compile(r"^character varying(?:\((\d+)\))?$")


def _type_problem(column: Column, db_type: str) -> Optional[str]:
    """Why the database type can't hold what the orchestrator reads and writes."""
    t = column.type
    # Most specific first: ENUM and Text are Strings, BigInteger is an Integer.
    if isinstance(t, ENUM):
        expected = t.name
    elif isinstance(t, BigInteger):
        expected = "bigint"
    elif isinstance(t, Integer):
        expected = "integer"
    elif isinstance(t, Float):
        expected = "double precision"
    elif isinstance(t, Boolean):
        expected = "boolean"
    elif isinstance(t, Text):
        expected = "text"
    elif isinstance(t, String):
        match = _VARCHAR.match(db_type)
        if not match:
            return f"is {db_type}, expected character varying({t.length})"
        if match.group(1) and t.length and int(match.group(1)) < t.length:
            return f"is {db_type}, too short for character varying({t.length})"
        return None
    elif isinstance(t, DateTime):
        expected = (
            "timestamp with time zone" if t.timezone else "timestamp without time zone"
        )
    else:  # pragma: no cover - a type the check doesn't know yet
        return f"has type {t!r}, which the schema check can't compare"
    return None if db_type == expected else f"is {db_type}, expected {expected}"


def compare(
    db_columns: list[DbColumn],
    enum_labels: dict[str, set[str]],
    metadata: MetaData = orchestrator_metadata,
) -> list[str]:
    """Every way the database falls short of the orchestrator's tables."""
    found = {(c.table, c.name): c for c in db_columns}
    tables = {c.table for c in db_columns}
    problems = []
    for table in metadata.tables.values():
        if table.name not in tables:
            problems.append(f"table {table.name} is missing")
            continue
        for column in table.columns:
            where = f"{table.name}.{column.name}"
            db = found.get((table.name, column.name))
            if db is None:
                problems.append(f"{where} is missing")
                continue
            type_problem = _type_problem(column, db.type)
            if type_problem:
                problems.append(f"{where} {type_problem}")
            if column.nullable == db.not_null:
                problems.append(
                    f"{where} is {'NOT NULL' if db.not_null else 'nullable'} in the "
                    f"database but {'nullable' if column.nullable else 'NOT NULL'} here"
                )
            if isinstance(column.type, ENUM):
                unknown = set(column.type.enums) - enum_labels.get(db.type, set())
                if unknown:
                    problems.append(
                        f"{where}: enum {db.type} lacks {', '.join(sorted(unknown))}"
                    )
            if not db.can_select:
                problems.append(f"{where}: no SELECT privilege")
            if writes_column(column) and not db.can_update:
                problems.append(f"{where}: no UPDATE privilege")
        if writes_table(table):
            if not any(c.can_insert for c in db_columns if c.table == table.name):
                problems.append(f"{table.name}: no INSERT privilege")
    return problems


_COLUMNS = text("""
    SELECT c.relname AS table_name,
           a.attname AS column_name,
           format_type(a.atttypid, a.atttypmod) AS type,
           a.attnotnull AS not_null,
           has_column_privilege(c.oid, a.attnum, 'SELECT') AS can_select,
           has_column_privilege(c.oid, a.attnum, 'UPDATE') AS can_update,
           has_table_privilege(c.oid, 'INSERT') AS can_insert
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND c.relname = ANY(:tables)
       AND a.attnum > 0
       AND NOT a.attisdropped
    """)

_ENUMS = text("""
    SELECT t.typname, e.enumlabel
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      JOIN pg_namespace n ON n.oid = t.typnamespace
     WHERE n.nspname = 'public'
    """)


async def schema_revision(conn: AsyncConnection) -> Optional[str]:
    """The app's alembic revision, or None if the table is missing or unreadable."""
    exists = await conn.scalar(
        text(
            "SELECT has_table_privilege(oid, 'SELECT') FROM pg_class "
            "WHERE oid = to_regclass('public.alembic_version')"
        )
    )
    if not exists:
        return None
    return await conn.scalar(text("SELECT version_num FROM alembic_version"))


async def check_schema(
    conn: AsyncConnection, metadata: MetaData = orchestrator_metadata
) -> list[str]:
    """Problems with the database for the current role; empty when all is well."""
    rows = (await conn.execute(_COLUMNS, {"tables": list(metadata.tables)})).mappings()
    db_columns = [
        DbColumn(
            table=r["table_name"],
            name=r["column_name"],
            type=r["type"],
            not_null=r["not_null"],
            can_select=r["can_select"],
            can_update=r["can_update"],
            can_insert=r["can_insert"],
        )
        for r in rows
    ]
    labels: dict[str, set[str]] = {}
    for typname, label in await conn.execute(_ENUMS):
        labels.setdefault(typname, set()).add(label)
    return compare(db_columns, labels, metadata)
