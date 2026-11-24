import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from servicex_orchestrator.config import did_finder_task_queue
    from servicex_orchestrator.models import (
        AUTH_FAILED,
        BAD_DID,
        DATASET_NOT_FOUND,
        LOOKUP_BAD_NAME,
        LOOKUP_COMPLETE,
        LOOKUP_DOES_NOT_EXIST,
        LOOKUP_INTERNAL_FAILURE,
        LookupInput,
        LookupSummary,
        MarkDatasetFailedInput,
    )
    from servicex_orchestrator.workflows.common import (
        error_type,
        orchestrator_activity,
        signal_workflow,
    )

# Plan §5.1
LOOKUP_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=10,
    non_retryable_error_types=[DATASET_NOT_FOUND, BAD_DID, AUTH_FAILED],
)

FAILURE_STATUS = {
    DATASET_NOT_FOUND: LOOKUP_DOES_NOT_EXIST,
    BAD_DID: LOOKUP_BAD_NAME,
}


@workflow.defn
class DatasetLookupWorkflow:
    """One DID-finder lookup, shared by every request for the dataset (plan §4.2).

    Its id is `dataset-<dataset_id>`. Requests start it, or join the one already
    running, with signal-with-start of `subscribe(<their workflow id>)`. It forwards
    the lookup's progress to every subscriber as `files_available(hwm)` and ends with
    `lookup_finished(status, hwm)`. The dataset row is the cache, so the workflow ends
    when the lookup does.
    """

    @workflow.init
    def __init__(self, input: LookupInput) -> None:
        # Shared by many requests, so logs are keyed on the dataset, like the DID
        # finders' own logs.
        self._log_extra = {"dataset_id": input.dataset_id}
        # A dict, not a set: iteration order must not depend on string hashing,
        # or a replay on another worker could signal in a different order.
        self._subscribers: dict[str, None] = {}
        self._hwm = 0
        self._status: Optional[str] = None

    @workflow.signal
    async def subscribe(self, subscriber_workflow_id: str) -> None:
        if subscriber_workflow_id in self._subscribers:
            return
        self._subscribers[subscriber_workflow_id] = None
        workflow.logger.info(
            "Subscriber %s joined", subscriber_workflow_id, extra=self._log_extra
        )
        # A late subscriber catches up straight away.
        if self._status is not None:
            await self._notify(
                subscriber_workflow_id, "lookup_finished", self._status, self._hwm
            )
        elif self._hwm:
            await self._notify(subscriber_workflow_id, "files_available", self._hwm)

    @workflow.signal
    async def progress(self, hwm: int) -> None:
        """Sent by the lookup activity each time it commits a batch of files."""
        if hwm <= self._hwm:
            return
        self._hwm = hwm
        await self._broadcast("files_available", hwm)

    @workflow.run
    async def run(self, input: LookupInput) -> str:
        await orchestrator_activity("mark_dataset_looking", input.dataset_id)
        try:
            summary: LookupSummary = await workflow.execute_activity(
                "lookup_dataset",
                input,
                result_type=LookupSummary,
                task_queue=did_finder_task_queue(input.did_scheme),
                start_to_close_timeout=timedelta(hours=6),
                heartbeat_timeout=timedelta(minutes=2),
                schedule_to_start_timeout=timedelta(minutes=15),
                retry_policy=LOOKUP_RETRY,
            )
        except ActivityError as err:
            kind, message = error_type(err)
            status = FAILURE_STATUS.get(kind, LOOKUP_INTERNAL_FAILURE)
            workflow.logger.warning(
                "Lookup of %s://%s failed (%s: %s)",
                input.did_scheme,
                input.did,
                kind,
                message,
                extra=self._log_extra,
            )
            await orchestrator_activity(
                "mark_dataset_failed",
                MarkDatasetFailedInput(input.dataset_id, status, f"{kind}: {message}"),
            )
        else:
            await orchestrator_activity(
                "mark_dataset_complete", input.dataset_id, summary
            )
            self._hwm = max(self._hwm, summary.max_file_id)
            status = LOOKUP_COMPLETE

        self._status = status
        await self._broadcast("lookup_finished", status, self._hwm)
        # Let any subscribe that raced the end get its reply before we close.
        await workflow.wait_condition(workflow.all_handlers_finished)
        return status

    async def _broadcast(self, signal: str, *args) -> None:
        await asyncio.gather(
            *(self._notify(sub, signal, *args) for sub in list(self._subscribers))
        )

    async def _notify(self, subscriber: str, signal: str, *args) -> None:
        if not await signal_workflow(subscriber, signal, *args):
            # The request is over (finished or canceled); stop telling it things.
            self._subscribers.pop(subscriber, None)
