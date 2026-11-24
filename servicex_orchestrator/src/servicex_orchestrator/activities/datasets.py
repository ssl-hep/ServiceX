"""The dataset cache activities: read a dataset row and record its lookup.

The app creates `datasets` rows at submit and owns `files` (the DID finders PUT files
to it), so these only read the row and write the orchestrator's columns:
`lookup_status`, `n_files`, `size`, `events` and `last_updated`. Each activity is one
idempotent statement (see the README, "Rules for DB activities").
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity
from temporalio.exceptions import ApplicationError

from servicex_orchestrator.db.tables import datasets, files
from servicex_orchestrator.models import (
    DATASET_MISSING,
    LOOKUP_COMPLETE,
    LOOKUP_FAILURE_STATUSES,
    DatasetInfo,
    GetDatasetInput,
    LookupSummary,
    MarkDatasetFailedInput,
)

LOOKUP_LOOKING = "looking"


def utc_now() -> datetime:
    """`datasets.last_updated` is a naive timestamp holding UTC, as the app writes it."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _file_count(dataset_id: int):
    return (
        select(func.count())
        .select_from(files)
        .where(files.c.dataset_id == dataset_id)
        .scalar_subquery()
    )


def _file_sum(column, dataset_id: int):
    return (
        select(func.coalesce(func.sum(column), 0))
        .where(files.c.dataset_id == dataset_id)
        .scalar_subquery()
    )


class DatasetActivities:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def _read(self, dataset_id: int) -> DatasetInfo:
        """The row's lookup status and what its files table holds, in one SELECT."""
        max_file_id = (
            select(func.max(files.c.id))
            .where(files.c.dataset_id == dataset_id)
            .scalar_subquery()
        )
        statement = select(
            datasets.c.lookup_status,
            datasets.c.stale,
            _file_count(dataset_id).label("n_files"),
            max_file_id.label("max_file_id"),
        ).where(datasets.c.id == dataset_id)
        async with self.engine.connect() as conn:
            row = (await conn.execute(statement)).one_or_none()
        if row is None:
            raise ApplicationError(
                f"Dataset {dataset_id} does not exist",
                type=DATASET_MISSING,
                non_retryable=True,
            )
        if row.stale:
            # The app picked this row at submit, before it was marked stale (deleted).
            # Its files are kept, and the lookup is keyed on the row id, so this
            # request carries on with it. New requests get a new row.
            activity.logger.warning(
                "Dataset %s was marked stale after the request was submitted; "
                "using it anyway",
                dataset_id,
            )
        return DatasetInfo(
            dataset_id=dataset_id,
            lookup_status=row.lookup_status,
            n_files_known=row.n_files,
            max_file_id=row.max_file_id or 0,
        )

    @activity.defn
    async def get_or_create_dataset(self, input: GetDatasetInput) -> DatasetInfo:
        """Read the request's dataset row; `complete` is a cache hit.

        The app already created the row at submit (a file-list dataset is created
        `complete` with its files), so nothing is created here. The name is kept
        because the workflows call it by name.
        """
        info = await self._read(input.dataset_id)
        activity.logger.info(
            "Dataset %s (%s://%s) is %s with %d files (max id %d)",
            input.dataset_id,
            input.did_scheme,
            input.did,
            info.lookup_status,
            info.n_files_known,
            info.max_file_id,
        )
        return info

    @activity.defn
    async def read_dataset(self, dataset_id: int) -> DatasetInfo:
        """Read a dataset row, for DatasetLookupWorkflow to skip a finished lookup."""
        return await self._read(dataset_id)

    @activity.defn
    async def mark_dataset_looking(self, dataset_id: int) -> None:
        # Never un-complete a row: a late (zombie) attempt must not undo
        # mark_dataset_complete.
        statement = (
            update(datasets)
            .where(
                datasets.c.id == dataset_id,
                datasets.c.lookup_status != LOOKUP_COMPLETE,
            )
            .values(lookup_status=LOOKUP_LOOKING)
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(statement)
        activity.logger.info(
            "Dataset %s marked looking (%d row)",
            dataset_id,
            result.rowcount,
            extra={"dataset_id": dataset_id},
        )

    @activity.defn
    async def mark_dataset_complete(
        self, dataset_id: int, summary: LookupSummary
    ) -> None:
        """Mark the lookup complete, with totals counted from the dataset's files.

        Counted, not taken from the summary: the request transforms what is in
        `files`, and the summary covers only the last attempt and counts a file the
        finder yields twice. Absolute values, so running this twice is harmless.
        """
        statement = (
            update(datasets)
            .where(datasets.c.id == dataset_id)
            .values(
                lookup_status=LOOKUP_COMPLETE,
                n_files=_file_count(dataset_id),
                size=_file_sum(files.c.file_size, dataset_id),
                events=_file_sum(files.c.file_events, dataset_id),
                last_updated=utc_now(),
            )
            .returning(datasets.c.n_files, datasets.c.size, datasets.c.events)
        )
        async with self.engine.begin() as conn:
            row = (await conn.execute(statement)).one_or_none()
        extra = {"dataset_id": dataset_id}
        if row is None:
            raise ApplicationError(
                f"Dataset {dataset_id} does not exist",
                type=DATASET_MISSING,
                non_retryable=True,
            )
        activity.logger.info(
            "Dataset %s complete: %d files, %d bytes, %d events",
            dataset_id,
            row.n_files,
            row.size,
            row.events,
            extra=extra,
        )
        if (row.n_files, row.size, row.events) != (
            summary.n_files,
            summary.size_bytes,
            summary.events,
        ):
            activity.logger.warning(
                "Dataset %s: the DID finder reported %d files, %d bytes, %d events "
                "for its last attempt; the dataset holds %d files, %d bytes, "
                "%d events",
                dataset_id,
                summary.n_files,
                summary.size_bytes,
                summary.events,
                row.n_files,
                row.size,
                row.events,
                extra=extra,
            )

    @activity.defn
    async def mark_dataset_failed(self, input: MarkDatasetFailedInput) -> None:
        """Record a failed lookup. The app has no column for the message, so it goes
        to the dataset's log records (shown on the dataset page)."""
        extra = {"dataset_id": input.dataset_id}
        if input.status not in LOOKUP_FAILURE_STATUSES:
            raise ApplicationError(
                f"Not a dataset failure status: {input.status!r}",
                type="InvalidDatasetStatus",
                non_retryable=True,
            )
        statement = (
            update(datasets)
            .where(datasets.c.id == input.dataset_id)
            .values(lookup_status=input.status, last_updated=utc_now())
        )
        async with self.engine.begin() as conn:
            await conn.execute(statement)
        activity.logger.error(
            "Dataset lookup failed (%s): %s",
            input.status,
            input.message,
            extra=extra,
        )

    def all(self) -> list:
        return [
            self.get_or_create_dataset,
            self.read_dataset,
            self.mark_dataset_looking,
            self.mark_dataset_complete,
            self.mark_dataset_failed,
        ]
