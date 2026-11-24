"""Request bookkeeping the orchestrator does before any file is transformed.

It writes only its own `requests` columns (see the README, "One writer per column"),
one idempotent statement per activity.
"""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity

from servicex_orchestrator.db.tables import requests
from servicex_orchestrator.models import (
    REQUEST_RUNNING,
    MarkRequestRunningInput,
    RecordWorkflowInput,
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

    def all(self) -> list:
        return [self.record_request_workflow, self.mark_request_running]
