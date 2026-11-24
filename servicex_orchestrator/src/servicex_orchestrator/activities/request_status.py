"""The orchestrator's bookkeeping on the `requests` row, from submit to finish.

It writes only its own `requests` columns (see the README, "One writer per column"),
one idempotent statement per activity. The workflow holds the counters and the status
and passes them in as absolute values.
"""

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity

from servicex_orchestrator.activities.datasets import utc_now
from servicex_orchestrator.db.tables import requests
from servicex_orchestrator.models import (
    REQUEST_RUNNING,
    FinalizeInput,
    MarkRequestRunningInput,
    RecordWorkflowInput,
    RequestProgressInput,
)

# Statuses of a request that hasn't finished. mark_request_running touches only
# these, so it never revives a request that already finished or was canceled.
# "running" is among them: submit already sets it for a complete dataset, and the
# file count still has to be written.
NOT_FINISHED = ("submitted", "pending_lookup", "lookup", "running")


class RequestActivities:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    @activity.defn
    async def record_request_workflow(self, input: RecordWorkflowInput) -> None:
        statement = (
            update(requests)
            .where(requests.c.request_id == input.request_id)
            .values(
                workflow_id=input.workflow_id,
                workflow_run_id=input.workflow_run_id,
            )
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(statement)
        if result.rowcount == 0:
            activity.logger.warning(
                "No request %s to record workflow %s on",
                input.request_id,
                input.workflow_id,
            )

    @activity.defn
    async def mark_request_running(self, input: MarkRequestRunningInput) -> None:
        statement = (
            update(requests)
            .where(
                requests.c.request_id == input.request_id,
                requests.c.status.in_(NOT_FINISHED),
            )
            .values(status=REQUEST_RUNNING, files=input.files)
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(statement)
        if result.rowcount:
            activity.logger.info(
                "Request %s running with %d files", input.request_id, input.files
            )
        else:
            activity.logger.info(
                "Request %s not marked running: missing, or already finished",
                input.request_id,
            )

    @activity.defn
    async def record_request_progress(self, input: RequestProgressInput) -> None:
        """Write the request's running totals while it runs.

        Absolute values, but never lower than what is there: batches finish
        concurrently, so two of these (or a late zombie attempt) can land out of
        order. Never touches a finished request, so it can't undo finalize_request.
        """
        statement = (
            update(requests)
            .where(
                requests.c.request_id == input.request_id,
                requests.c.status.in_(NOT_FINISHED),
            )
            .values(
                files_completed=func.greatest(
                    requests.c.files_completed, input.files_completed
                ),
                files_failed=func.greatest(requests.c.files_failed, input.files_failed),
                total_events=func.greatest(
                    func.coalesce(requests.c.total_events, 0), input.total_events
                ),
                total_bytes=func.greatest(
                    func.coalesce(requests.c.total_bytes, 0), input.total_bytes
                ),
            )
        )
        async with self.engine.begin() as conn:
            await conn.execute(statement)

    @activity.defn
    async def finalize_request(self, input: FinalizeInput) -> None:
        """Record how the request ended, once.

        Only a request that hasn't finished is updated: a retry finds it finished
        and leaves finish_time as first written, and a request the app already
        ended (canceled) keeps the app's record.
        """
        values = dict(
            status=input.status,
            finish_time=utc_now(),
            files_completed=input.files_completed,
            files_failed=input.files_failed,
            total_events=input.total_events,
            total_bytes=input.total_bytes,
        )
        if input.message is not None:
            values["failure_description"] = input.message
        statement = (
            update(requests)
            .where(
                requests.c.request_id == input.request_id,
                requests.c.status.in_(NOT_FINISHED),
            )
            .values(**values)
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(statement)
        if result.rowcount:
            activity.logger.info(
                "Request %s %s: %d files completed, %d failed%s",
                input.request_id,
                input.status,
                input.files_completed,
                input.files_failed,
                f" ({input.message})" if input.message else "",
            )
        else:
            activity.logger.info(
                "Request %s not finalized as %s: missing, or already finished",
                input.request_id,
                input.status,
            )

    def all(self) -> list:
        return [
            self.record_request_workflow,
            self.mark_request_running,
            self.record_request_progress,
            self.finalize_request,
        ]
