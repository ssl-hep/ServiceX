"""Seeding a Postgres migrated by the app, for the tests that need one (tests/db,
tests/e2e). They need the database scripts/schema-contract-test.sh (or
lookup-e2e-test.sh) sets up, with the orchestrator role, named by CONTRACT_ADMIN_URL
and CONTRACT_ORCHESTRATOR_URL.
"""

import os
import uuid
from dataclasses import dataclass, field

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from servicex_orchestrator.db.engine import async_url

ADMIN_URL = os.environ.get("CONTRACT_ADMIN_URL")
ORCHESTRATOR_URL = os.environ.get("CONTRACT_ORCHESTRATOR_URL")


# Test modules that need the database start with `pytestmark = NEEDS_DB`.
NEEDS_DB = [
    pytest.mark.db,
    pytest.mark.skipif(
        not (ADMIN_URL and ORCHESTRATOR_URL),
        reason="needs CONTRACT_ADMIN_URL and CONTRACT_ORCHESTRATOR_URL "
        "(run scripts/schema-contract-test.sh)",
    ),
]


# The app's upsert of DID-finder files (PUT .../<dataset_id>/files), in SQL.
UPSERT_FILE = text(
    "INSERT INTO files (dataset_id, paths, file_key, adler32, file_size, file_events) "
    "VALUES (:d, :paths, :key, 'xxx', :size, :events) "
    "ON CONFLICT (dataset_id, file_key) DO UPDATE SET paths = EXCLUDED.paths, "
    "adler32 = EXCLUDED.adler32, file_size = EXCLUDED.file_size, "
    "file_events = EXCLUDED.file_events RETURNING id"
)


@dataclass
class Seeder:
    """Makes datasets, files and requests the way the app does, as the admin, and
    deletes them afterwards (the orchestrator role can't)."""

    admin: AsyncEngine
    datasets: list[int] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)

    async def dataset(
        self, status: str = "looking", stale: bool = False, did_finder: str = "rucio"
    ) -> int:
        async with self.admin.begin() as conn:
            dataset_id = await conn.scalar(
                text(
                    "INSERT INTO datasets (name, last_used, last_updated, did_finder, "
                    "lookup_status, stale, n_files, size, events) VALUES (:n, now(), "
                    "now(), :f, :s, :stale, 0, 0, 0) RETURNING id"
                ),
                {
                    "n": f"{did_finder}://db-test:{uuid.uuid4()}",
                    "f": did_finder,
                    "s": status,
                    "stale": stale,
                },
            )
        self.datasets.append(dataset_id)
        return dataset_id

    async def files(
        self, dataset_id: int, keys, size: int = 1000, events: int = 10
    ) -> list[int]:
        """Upsert one file per key; returns the ids (new or existing)."""
        async with self.admin.begin() as conn:
            return [
                await conn.scalar(
                    UPSERT_FILE,
                    {
                        "d": dataset_id,
                        "paths": f"root://se//{key}",
                        "key": key,
                        "size": size,
                        "events": events,
                    },
                )
                for key in keys
            ]

    async def request(self, dataset_id: int, status: str = "lookup") -> str:
        request_id = str(uuid.uuid4())
        async with self.admin.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO requests (request_id, submit_time, did, did_id, "
                    "result_destination, result_format, files, files_completed, "
                    "files_failed, status, title) VALUES (:r, now(), 'db-test', :d, "
                    "'object-store', 'parquet', 0, 0, 0, :s, 'db-test')"
                ),
                {"r": request_id, "d": dataset_id, "s": status},
            )
        self.requests.append(request_id)
        return request_id

    async def execute(self, sql: str, **params) -> None:
        """Run a statement and commit it."""
        async with self.admin.begin() as conn:
            await conn.execute(text(sql), params)

    async def row(self, sql: str, **params):
        async with self.admin.connect() as conn:
            return (await conn.execute(text(sql), params)).one()

    async def scalar(self, sql: str, **params):
        async with self.admin.connect() as conn:
            return await conn.scalar(text(sql), params)

    async def cleanup(self) -> None:
        async with self.admin.begin() as conn:
            for request_id in self.requests:
                await conn.execute(
                    text("DELETE FROM requests WHERE request_id = :r"),
                    {"r": request_id},
                )
            for dataset_id in self.datasets:
                await conn.execute(
                    text("DELETE FROM requests WHERE did_id = :d"), {"d": dataset_id}
                )
                await conn.execute(
                    text("DELETE FROM files WHERE dataset_id = :d"), {"d": dataset_id}
                )
                await conn.execute(
                    text("DELETE FROM datasets WHERE id = :d"), {"d": dataset_id}
                )


def engine(url: str) -> AsyncEngine:
    return create_async_engine(async_url(url), poolclass=NullPool)
