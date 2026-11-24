"""Schema contract: the app's migrations vs. the orchestrator's tables and role.

Needs a Postgres migrated by the app and the orchestrator role created by
`flask orchestrator-db-role`; scripts/schema-contract-test.sh sets one up and runs
these. Skipped otherwise.

- The orchestrator's tables match the database (columns, types, nullability, enum
  labels) and the role has the privileges they need: `check_schema` finds nothing.
- The statements the orchestrator's activities will run succeed as its role.
- Everything else is refused: writes to app-owned columns, DELETE, DDL.
"""

import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from servicex_orchestrator.db.engine import async_url
from servicex_orchestrator.db.schema_check import check_schema, schema_revision
from servicex_orchestrator.db.tables import (
    datasets,
    files,
    requests,
    transform_result,
)

ADMIN_URL = os.environ.get("CONTRACT_ADMIN_URL")
ORCHESTRATOR_URL = os.environ.get("CONTRACT_ORCHESTRATOR_URL")

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(
        not (ADMIN_URL and ORCHESTRATOR_URL),
        reason="needs CONTRACT_ADMIN_URL and CONTRACT_ORCHESTRATOR_URL "
        "(run scripts/schema-contract-test.sh)",
    ),
]

INSUFFICIENT_PRIVILEGE = "42501"


def _engine(url):
    return create_async_engine(async_url(url), poolclass=NullPool)


@pytest.fixture
async def admin():
    engine = _engine(ADMIN_URL)
    yield engine
    await engine.dispose()


@pytest.fixture
async def orchestrator():
    engine = _engine(ORCHESTRATOR_URL)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded(admin):
    """A dataset with two files and a request on it, made the way the app makes them."""
    request_id = str(uuid.uuid4())
    async with admin.begin() as conn:
        dataset_id = await conn.scalar(
            text(
                "INSERT INTO datasets (name, last_used, last_updated, did_finder, "
                "lookup_status, stale, n_files) VALUES (:n, now(), now(), 'rucio', "
                "'looking', false, 0) RETURNING id"
            ),
            {"n": f"rucio://contract:{request_id}"},
        )
        file_ids = [
            await conn.scalar(
                text(
                    "INSERT INTO files (dataset_id, paths, file_key) "
                    "VALUES (:d, :p, :k) RETURNING id"
                ),
                {"d": dataset_id, "p": f"root://se//f{i}.root", "k": f"contract:f{i}"},
            )
            for i in range(2)
        ]
        await conn.execute(
            text(
                "INSERT INTO requests (request_id, submit_time, did, did_id, "
                "result_destination, result_format, files, files_completed, "
                "files_failed, status, title) VALUES (:r, now(), :did, :d, "
                "'object-store', 'parquet', 2, 0, 0, 'submitted', 'contract')"
            ),
            {"r": request_id, "did": f"rucio://contract:{request_id}", "d": dataset_id},
        )
    yield {"request_id": request_id, "dataset_id": dataset_id, "file_ids": file_ids}
    async with admin.begin() as conn:
        await conn.execute(
            text("DELETE FROM transform_result WHERE request_id = :r"),
            {"r": request_id},
        )
        await conn.execute(
            text("DELETE FROM requests WHERE request_id = :r"), {"r": request_id}
        )
        await conn.execute(
            text("DELETE FROM files WHERE dataset_id = :d"), {"d": dataset_id}
        )
        await conn.execute(
            text("DELETE FROM datasets WHERE id = :d"), {"d": dataset_id}
        )


async def _rolled_back(engine, statements):
    """Run the statements in one transaction, roll it back, return the results."""
    async with engine.connect() as conn:
        async with conn.begin() as tx:
            results = [await conn.execute(s) for s in statements]
            await tx.rollback()
    return results


# ----- the schema matches -------------------------------------------------------


async def test_schema_matches_orchestrator_tables(orchestrator):
    async with orchestrator.connect() as conn:
        assert await schema_revision(conn) is not None
        assert await check_schema(conn) == []


async def test_check_schema_sees_grants_as_admin_too(admin):
    # The superuser has every privilege, so only shape problems could show here.
    async with admin.connect() as conn:
        assert await check_schema(conn) == []


# ----- what the orchestrator does -----------------------------------------------


async def test_reads(orchestrator, seeded):
    rows = await _rolled_back(
        orchestrator,
        [
            select(datasets).where(datasets.c.id == seeded["dataset_id"]),
            select(files)
            .where(files.c.dataset_id == seeded["dataset_id"], files.c.id > 0)
            .order_by(files.c.id),
            select(requests).where(requests.c.request_id == seeded["request_id"]),
        ],
    )
    dataset, file_rows, request = (r.all() for r in rows)
    assert dataset[0].lookup_status == "looking"
    assert [f.file_key for f in file_rows] == ["contract:f0", "contract:f1"]
    assert request[0].status == "submitted"


async def test_updates_its_dataset_columns(orchestrator, seeded):
    (result,) = await _rolled_back(
        orchestrator,
        [
            update(datasets)
            .where(datasets.c.id == seeded["dataset_id"])
            .values(
                lookup_status="internal_failure",
                n_files=2,
                size=2_000_000,
                events=20_000,
                last_updated=datetime.now(),
            )
        ],
    )
    assert result.rowcount == 1


async def test_updates_its_request_columns(orchestrator, seeded):
    (result,) = await _rolled_back(
        orchestrator,
        [
            update(requests)
            .where(requests.c.request_id == seeded["request_id"])
            .values(
                status="complete",
                finish_time=datetime.now(),
                files_completed=2,
                files_failed=0,
                workflow_id=f"transform-{seeded['request_id']}",
                workflow_run_id=str(uuid.uuid4()),
            )
        ],
    )
    assert result.rowcount == 1


async def test_writes_and_upserts_transform_results(orchestrator, seeded):
    file_id = seeded["file_ids"][0]
    row = dict(
        file_id=file_id,
        file_path="root://se//f0.root",
        request_id=seeded["request_id"],
        transform_status="failure",
        created_at=datetime.now(),
    )
    upsert = pg_insert(transform_result).values(
        **{**row, "transform_status": "success", "s3_object_name": "abc.parquet"}
    )
    upsert = upsert.on_conflict_do_update(
        index_elements=[transform_result.c.file_id, transform_result.c.request_id],
        set_={
            "transform_status": upsert.excluded.transform_status,
            "s3_object_name": upsert.excluded.s3_object_name,
        },
    )
    _, _, after = await _rolled_back(
        orchestrator,
        [
            insert(transform_result).values(**row),
            upsert,
            select(transform_result.c.transform_status).where(
                transform_result.c.request_id == seeded["request_id"]
            ),
        ],
    )
    assert after.scalars().all() == ["success"]


# ----- what it may not do -------------------------------------------------------

REFUSED = {
    # App-owned columns
    "update requests.title": "UPDATE requests SET title = 'x' WHERE request_id = :r",
    "update requests.did_id": "UPDATE requests SET did_id = did_id WHERE request_id = :r",
    "update requests.files": "UPDATE requests SET files = 0 WHERE request_id = :r",
    "update datasets.name": "UPDATE datasets SET name = 'x' WHERE id = :d",
    "update datasets.stale": "UPDATE datasets SET stale = true WHERE id = :d",
    "read requests.selection": "SELECT selection FROM requests WHERE request_id = :r",
    # files are written by the app (for the DID finders)
    "update files": "UPDATE files SET file_key = 'x' WHERE dataset_id = :d",
    "insert files": "INSERT INTO files (dataset_id, paths) VALUES (:d, 'x')",
    "insert requests": "INSERT INTO requests (request_id) VALUES ('x')",
    "insert datasets": "INSERT INTO datasets (name) VALUES ('x')",
    # No DELETE anywhere
    "delete transform_result": "DELETE FROM transform_result WHERE request_id = :r",
    "delete requests": "DELETE FROM requests WHERE request_id = :r",
    "delete files": "DELETE FROM files WHERE dataset_id = :d",
    "delete datasets": "DELETE FROM datasets WHERE id = :d",
    "truncate transform_result": "TRUNCATE transform_result",
    # Tables it has no business with
    "read users": "SELECT * FROM users",
    "read log_messages": "SELECT * FROM log_messages",
    # No DDL
    "create table": "CREATE TABLE orchestrator_scratch (id integer)",
    "alter table": "ALTER TABLE datasets ADD COLUMN orchestrator_scratch integer",
    "create index": "CREATE INDEX ON transform_result (transform_status)",
    "drop table": "DROP TABLE transform_result",
    "alter sequence": "ALTER SEQUENCE transform_result_id_seq RESTART",
}


def _sqlstate(err: DBAPIError):
    orig = err.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


@pytest.mark.parametrize("sql", REFUSED.values(), ids=REFUSED.keys())
async def test_refused(orchestrator, seeded, sql):
    params = {"r": seeded["request_id"], "d": seeded["dataset_id"]}
    bound = {k: v for k, v in params.items() if f":{k}" in sql}
    with pytest.raises(DBAPIError) as err:
        async with orchestrator.connect() as conn:
            async with conn.begin() as tx:
                await conn.execute(text(sql), bound)
                await tx.rollback()
    # 42501, or for ALTER/DROP on someone else's table 42501 as "must be owner".
    assert _sqlstate(err.value) == INSUFFICIENT_PRIVILEGE, err.value


async def test_cannot_delete_even_with_core(orchestrator, seeded):
    with pytest.raises(DBAPIError) as err:
        await _rolled_back(
            orchestrator,
            [delete(datasets).where(datasets.c.id == seeded["dataset_id"])],
        )
    assert _sqlstate(err.value) == INSUFFICIENT_PRIVILEGE
