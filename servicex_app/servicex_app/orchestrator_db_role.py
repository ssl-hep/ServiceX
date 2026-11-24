# Copyright (c) 2026, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""The Postgres role the Temporal orchestrator connects as, and what it may do.

The app owns the schema; the orchestrator reads and writes some of it directly. Every
column has exactly one writer, and this module is where the orchestrator's share is
written down. `flask orchestrator-db-role` (run by boot.sh right after
`flask db upgrade`) applies it on every boot:

- creates the role if it is missing and sets its password;
- revokes everything the role holds in schema public, then grants exactly what is
  listed below, in one transaction. A later migration therefore needs no grant
  bookkeeping: a table-level grant covers columns it adds, a column-level UPDATE never
  does, and a renamed or dropped column listed here makes the GRANT (and the boot)
  fail loudly instead of drifting.

To give the orchestrator a new column: add it in a migration, list it here, add it to
the orchestrator's `db/tables.py`, and run the schema contract test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from sqlalchemy import Engine, text

DEFAULT_ROLE = "servicex_orchestrator"

# Serializes concurrent app replicas booting at once (CREATE ROLE is not idempotent).
_ADVISORY_LOCK_KEY = 0x5E7C1CE0

ALL = "ALL"
Columns = Union[str, tuple[str, ...]]  # ALL, or a column list


@dataclass(frozen=True)
class TableGrant:
    select: Columns = ()
    update: Columns = ()
    insert: bool = False


# Reads: datasets and files whole, requests only where it filters or writes.
# Writes: the columns derived from workflow state, and transform_result entirely.
# UPDATE ... WHERE and INSERT ... ON CONFLICT need SELECT on the columns they read.
ORCHESTRATOR_TABLES: dict[str, TableGrant] = {
    "datasets": TableGrant(
        select=ALL,
        update=("lookup_status", "n_files", "size", "events", "last_updated"),
    ),
    "files": TableGrant(select=ALL),
    "requests": TableGrant(
        select=(
            "id",
            "request_id",
            "did_id",
            "status",
            "finish_time",
            "files",
            "files_completed",
            "files_failed",
            "total_events",
            "total_bytes",
            "failure_description",
            "workflow_id",
            "workflow_run_id",
        ),
        update=(
            "status",
            "finish_time",
            # The request's file count once its dataset is known (Temporal mode).
            "files",
            "files_completed",
            "files_failed",
            "total_events",
            "total_bytes",
            # Why the request ended, when it didn't complete (finalize_request).
            "failure_description",
            "workflow_id",
            "workflow_run_id",
        ),
    ),
    "transform_result": TableGrant(select=ALL, update=ALL, insert=True),
    # The orchestrator logs the schema revision it finds at startup.
    "alembic_version": TableGrant(select=ALL),
}

ORCHESTRATOR_SEQUENCES: dict[str, tuple[str, ...]] = {
    "transform_result_id_seq": ("USAGE", "SELECT"),
}

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _ident(name: str) -> str:
    if not _ROLE_NAME.match(name):
        raise ValueError(f"Not a plain lowercase Postgres identifier: {name!r}")
    return f'"{name}"'


def _quoted(name: str) -> str:
    """Any identifier, quoted (for names we read from Postgres, not ones we choose)."""
    return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
    # Postgres has standard_conforming_strings on by default (since 9.1), so doubling
    # single quotes is the whole escape. ALTER ROLE takes no bind parameters.
    if "\x00" in value:
        raise ValueError("Password may not contain NUL")
    return "'" + value.replace("'", "''") + "'"


def _privilege(name: str, columns: Columns) -> str:
    if columns == ALL:
        return name
    return f"{name} ({', '.join(_ident(c) for c in columns)})"


def grant_statements(role: str, database: str) -> list[str]:
    """The REVOKE/GRANT statements that reset the role to exactly its spec."""
    r = _ident(role)
    statements = [
        f"GRANT CONNECT ON DATABASE {_quoted(database)} TO {r}",
        # Postgres < 15 lets every role CREATE in schema public. The app and Vector
        # connect as the superuser and Temporal uses its own databases, so nothing
        # else depends on it.
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"GRANT USAGE ON SCHEMA public TO {r}",
        # Also clears column-level privileges, so a dropped entry above takes effect.
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {r}",
    ]
    for table, grant in ORCHESTRATOR_TABLES.items():
        privileges = []
        if grant.select:
            privileges.append(_privilege("SELECT", grant.select))
        if grant.insert:
            privileges.append("INSERT")
        if grant.update:
            privileges.append(_privilege("UPDATE", grant.update))
        statements.append(f"GRANT {', '.join(privileges)} ON TABLE {table} TO {r}")
    for sequence, privileges in ORCHESTRATOR_SEQUENCES.items():
        statements.append(
            f"GRANT {', '.join(privileges)} ON SEQUENCE {sequence} TO {r}"
        )
    return statements


def role_statements(role: str, password: str) -> list[str]:
    r = _ident(role)
    return [
        "DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {r} LOGIN; "
        "END IF; END $$",
        f"ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
        f"NOREPLICATION NOBYPASSRLS PASSWORD {_literal(password)}",
    ]


def apply(engine: Engine, role: str, password: str) -> None:
    """Create or update the orchestrator role and reset its grants, atomically."""
    if not password:
        raise ValueError("The orchestrator role needs a password")
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            f"The orchestrator needs Postgres; this app uses {engine.dialect.name}"
        )
    with engine.begin() as conn:
        if role == conn.execute(text("SELECT current_user")).scalar():
            raise ValueError(f"Refusing to restrict the app's own role {role!r}")
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
        )
        database = conn.execute(text("SELECT current_database()")).scalar()
        # A bare DBAPI cursor with no parameters: exec_driver_sql would still run
        # psycopg2's %-formatting, which a password containing % breaks.
        cursor = conn.connection.cursor()
        try:
            for statement in role_statements(role, password) + grant_statements(
                role, database
            ):
                cursor.execute(statement)
        finally:
            cursor.close()
