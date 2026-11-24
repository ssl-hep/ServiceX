"""The activities that hand a request its files and record what became of each.

`files` is the app's (the DID finders PUT them to it), so it is only read here;
`transform_result` is the orchestrator's entirely. Each activity is one idempotent
statement (see the README, "Rules for DB activities").
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity

from servicex_orchestrator.activities.datasets import utc_now
from servicex_orchestrator.db.tables import files, transform_result
from servicex_orchestrator.models import (
    FILE_SUCCESS,
    ClaimBatchInput,
    FileRef,
    RecordFileResultInput,
)

# transform_result.file_path is a varchar(512)
FILE_PATH_LENGTH = 512


def replicas_of(paths: str) -> list[str]:
    """The app stores a file's replicas comma-joined, in the DID finder's order."""
    return [p.strip() for p in paths.split(",") if p.strip()]


def file_key_of(file_id: int, file_key: Optional[str], replicas: list[str]) -> str:
    """A NULL file_key is a duplicate row from before the v1_10_0 migration, which
    backfilled each file's key from its first replica and left the duplicates NULL.
    Falling back to the same rule gives the duplicate its sibling's key, so both
    write the same output object rather than two copies of it."""
    if file_key is not None:
        return file_key
    fallback = replicas[0] if replicas else f"file-id:{file_id}"
    activity.logger.warning(
        "File %s has no file_key (a pre-migration duplicate); using %s",
        file_id,
        fallback,
    )
    return fallback


class FileActivities:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    @activity.defn
    async def claim_file_batch(self, input: ClaimBatchInput) -> list[FileRef]:
        """The dataset's next files past the request's cursor, up to the high-water
        mark.

        Not a claim in the DB: the workflow's cursor is what makes each file go to
        one batch. Files at or below the high-water mark are committed (the lookup
        signals only ids it has written), so reading the same range again returns
        the same ids.
        """
        statement = (
            select(files.c.id, files.c.file_key, files.c.paths)
            .where(
                files.c.dataset_id == input.dataset_id,
                files.c.id > input.after,
                files.c.id <= input.up_to,
            )
            .order_by(files.c.id)
            .limit(input.limit)
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(statement)).all()
        batch = []
        for row in rows:
            replicas = replicas_of(row.paths)
            batch.append(
                FileRef(
                    file_id=row.id,
                    file_key=file_key_of(row.id, row.file_key, replicas),
                    replicas=replicas,
                )
            )
        activity.logger.info(
            "Request %s: %d files of dataset %s with %d < id <= %d (limit %d)",
            input.request_id,
            len(batch),
            input.dataset_id,
            input.after,
            input.up_to,
            input.limit,
            extra={"request_id": input.request_id},
        )
        return batch

    @activity.defn
    async def record_file_result(self, input: RecordFileResultInput) -> None:
        """Upsert the file's transform_result row, with the columns the app's
        Celery-mode file-complete endpoint fills.

        The request's counters are not touched here: the request workflow writes
        them as absolute values (record_request_progress, finalize_request).
        """
        r = input.result
        if r.replica_used:
            file_path = r.replica_used[:FILE_PATH_LENGTH]
        else:
            # A file that failed for good never reports a replica: show its first.
            file_path = func.coalesce(
                select(
                    func.left(func.split_part(files.c.paths, ",", 1), FILE_PATH_LENGTH)
                )
                .where(files.c.id == r.file_id)
                .scalar_subquery(),
                "",
            )
        seconds = max(r.transform_seconds, 0.0)
        values = {
            "file_id": r.file_id,
            "request_id": input.request_id,
            "file_path": file_path,
            "transform_status": r.status,
            "transform_time": round(seconds),
            "total_events": r.events,
            "total_bytes": r.bytes,
            "avg_rate": r.events / seconds if seconds > 0 else 0.0,
            "s3_object_name": r.object_name,
        }
        statement = pg_insert(transform_result).values(created_at=utc_now(), **values)
        # created_at stays as first written: the results API pages on it.
        statement = statement.on_conflict_do_update(
            index_elements=[transform_result.c.file_id, transform_result.c.request_id],
            set_={name: statement.excluded[name] for name in values},
        )
        async with self.engine.begin() as conn:
            await conn.execute(statement)

        extra = {"request_id": input.request_id, "file_id": r.file_id}
        if r.status == FILE_SUCCESS:
            activity.logger.info(
                "File %s transformed to %s", r.file_id, r.object_name, extra=extra
            )
        else:
            # transform_result has no column for why; the request's log records do.
            activity.logger.error(
                "File %s failed (%s): %s",
                r.file_id,
                r.error_type,
                r.error_message,
                extra=extra,
            )

    def all(self) -> list:
        return [self.claim_file_batch, self.record_file_result]
