import asyncio
import dataclasses
import hashlib
from typing import Optional

from temporalio import workflow
from temporalio.exceptions import ChildWorkflowError, FailureError
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from servicex_orchestrator.models import (
        LOOKUP_BAD_NAME,
        LOOKUP_COMPLETE,
        LOOKUP_DOES_NOT_EXIST,
        REQUEST_BAD_DATASET,
        REQUEST_CANCELED,
        REQUEST_COMPLETE,
        REQUEST_FATAL,
        BatchResult,
        ClaimBatchInput,
        DatasetInfo,
        FileBatchInput,
        FileRef,
        FinalizeInput,
        GetDatasetInput,
        LookupInput,
        PoolInput,
        PoolSpec,
        StartLookupInput,
        TransformRequestInput,
        TransformRequestResult,
        TransformRequestState,
        TransformRequestStatus,
        TransformSpec,
    )
    from servicex_orchestrator.workflows.common import (
        orchestrator_activity,
        signal_workflow,
    )
    from servicex_orchestrator.workflows.file_batch import FileBatchWorkflow
    from servicex_orchestrator.workflows.pool_manager import PoolManagerWorkflow


def did_hash(scheme: str, did: str) -> str:
    """A digest of the DID, passed to `get_or_create_dataset` and the DID finders.

    Informational only: it is not a cache key. The app picks (or creates) the dataset
    row by name at submit, and the lookup workflow is keyed on that row's id. Note
    `did` already carries its scheme, so this hashes `rucio://rucio://...`; it is kept
    as is because the DID finders receive it.
    """
    return hashlib.sha256(f"{scheme}://{did}".encode()).hexdigest()


def request_workflow_id(request_id: str) -> str:
    return f"transform-{request_id}"


def pool_workflow_id(request_id: str) -> str:
    return f"pool-{request_id}"


@workflow.defn
class TransformRequestWorkflow:
    """Owns one transform request from dataset lookup to cleanup (plan §4.1).

    Id `transform-<request_id>`. It consumes the dataset's files by cursor: lookup
    signals carry only a high-water mark (the largest files.id written so far), and
    `claim_file_batch` reads the files past the cursor from the DB. A lost, repeated
    or out-of-order signal does no harm.
    """

    @workflow.init
    def __init__(self, input: TransformRequestInput) -> None:
        # Set up here, not in run(): signals that arrive with the first workflow task
        # are handled before run() starts.
        self._state = input.state or TransformRequestState()
        self._tuning = input.tuning
        self._in_flight = 0
        self._batch_tasks: set[asyncio.Task] = set()
        self._batches_this_run = 0

    # ----- signals and queries ---------------------------------------------------

    @workflow.signal
    def files_available(self, hwm: int) -> None:
        self._state.hwm = max(self._state.hwm, hwm)

    @workflow.signal
    def lookup_finished(self, status: str, hwm: int) -> None:
        self._state.hwm = max(self._state.hwm, hwm)
        if self._state.lookup_status is None:
            self._state.lookup_status = status

    @workflow.query
    def status(self) -> TransformRequestStatus:
        s = self._state
        return TransformRequestStatus(
            dataset_id=s.dataset_id,
            cursor=s.cursor,
            hwm=s.hwm,
            lookup_status=s.lookup_status,
            batches_in_flight=self._in_flight,
            files_dispatched=s.files_dispatched,
            files_completed=s.files_completed,
            files_failed=s.files_failed,
        )

    # ----- run -------------------------------------------------------------------

    @workflow.run
    async def run(self, input: TransformRequestInput) -> TransformRequestResult:
        s = self._state
        try:
            if not s.initialized:
                await self._find_dataset(input)
                s.initialized = True

            finished = await self._dispatch(input)
            if not finished:
                # Drained at a batch boundary; start a fresh history.
                await workflow.wait_condition(workflow.all_handlers_finished)
                workflow.continue_as_new(dataclasses.replace(input, state=s))

            status, message = self._final_status()
            await orchestrator_activity(
                "finalize_request",
                FinalizeInput(
                    input.request_id,
                    status,
                    s.files_completed,
                    s.files_failed,
                    message,
                ),
            )
            await self._stop_pool(input)
            await orchestrator_activity("cleanup_request", input.request_id)
            return TransformRequestResult(
                input.request_id, status, s.files_completed, s.files_failed
            )
        except asyncio.CancelledError:
            workflow.logger.info("Request %s canceled", input.request_id)
            for task in self._batch_tasks:
                task.cancel()
            await self._stop_pool(input)
            await orchestrator_activity(
                "finalize_request",
                FinalizeInput(
                    input.request_id,
                    REQUEST_CANCELED,
                    s.files_completed,
                    s.files_failed,
                    "canceled by user",
                ),
            )
            await orchestrator_activity("cleanup_request", input.request_id)
            raise

    async def _find_dataset(self, input: TransformRequestInput) -> None:
        """Check the dataset cache, and join (or start) its lookup if it is needed."""
        s = self._state
        key = did_hash(input.did_scheme, input.did)
        info: DatasetInfo = await orchestrator_activity(
            "get_or_create_dataset",
            GetDatasetInput(
                input.request_id, key, input.did, input.did_scheme, input.dataset_id
            ),
            result_type=DatasetInfo,
        )
        s.dataset_id = info.dataset_id
        if info.lookup_status == LOOKUP_COMPLETE:
            s.hwm = max(s.hwm, info.max_file_id)
            s.lookup_status = LOOKUP_COMPLETE
            return
        await orchestrator_activity(
            "start_dataset_lookup",
            StartLookupInput(
                lookup=LookupInput(key, input.did, input.did_scheme, s.dataset_id),
                subscriber_workflow_id=workflow.info().workflow_id,
            ),
        )

    async def _dispatch(self, input: TransformRequestInput) -> bool:
        """Start batch children until the request is done.

        Returns True when every file is accounted for (or the lookup failed), False
        when it is time to continue-as-new. In that case there are no batches in
        flight.
        """
        s = self._state
        t = self._tuning

        def lookup_failed() -> bool:
            return s.lookup_status not in (None, LOOKUP_COMPLETE)

        def want_continue_as_new() -> bool:
            return self._batches_this_run >= t.batches_per_run or (
                self._batches_this_run > 0
                and workflow.info().is_continue_as_new_suggested()
            )

        def finished() -> bool:
            if self._in_flight:
                return False
            return lookup_failed() or (
                s.lookup_status == LOOKUP_COMPLETE and s.cursor >= s.hwm
            )

        def can_dispatch() -> bool:
            return (
                not lookup_failed()
                and not want_continue_as_new()
                and s.cursor < s.hwm
                and self._in_flight < t.max_concurrent_batches
            )

        def drained_for_continue_as_new() -> bool:
            return want_continue_as_new() and self._in_flight == 0

        while True:
            await workflow.wait_condition(
                lambda: can_dispatch() or finished() or drained_for_continue_as_new()
            )
            if finished():
                return True
            if drained_for_continue_as_new():
                return False

            files: list[FileRef] = await orchestrator_activity(
                "claim_file_batch",
                ClaimBatchInput(
                    input.request_id,
                    s.dataset_id,
                    after=s.cursor,
                    up_to=s.hwm,
                    limit=t.batch_size,
                ),
                result_type=list[FileRef],
            )
            if not files:
                # No file ids between the cursor and the hwm.
                s.cursor = s.hwm
                continue
            s.cursor = files[-1].file_id
            await self._start_batch(input, files)

    async def _start_batch(
        self, input: TransformRequestInput, files: list[FileRef]
    ) -> None:
        s = self._state
        if not s.pool_started:
            # Only now, so we never launch pods for a dataset that turns out empty.
            await self._start_pool(input)
        s.batches_started += 1
        self._batches_this_run += 1
        s.files_dispatched += len(files)
        self._in_flight += 1
        task = asyncio.create_task(self._run_batch(input, s.batches_started, files))
        self._batch_tasks.add(task)
        task.add_done_callback(self._batch_tasks.discard)
        await self._send_backlog(input)

    async def _run_batch(
        self, input: TransformRequestInput, number: int, files: list[FileRef]
    ) -> None:
        s = self._state
        spec = TransformSpec(
            input.request_id, input.result_destination, input.result_format
        )
        try:
            result: BatchResult = await workflow.execute_child_workflow(
                FileBatchWorkflow.run,
                FileBatchInput(spec=spec, batch_number=number, files=files),
                id=f"{request_workflow_id(input.request_id)}-batch-{number}",
            )
            s.files_completed += result.files_completed
            s.files_failed += result.files_failed
            # TODO: fail fast (plan §7) when code errors pile up. The stubs never fail.
        except ChildWorkflowError as err:
            # Should not happen: the batch records every file. Count the batch as
            # failed so the request still finishes.
            workflow.logger.error("Batch %d failed: %s", number, err)
            s.files_failed += len(files)
        finally:
            self._in_flight -= 1
        await self._send_backlog(input)

    # ----- worker pool -----------------------------------------------------------

    async def _start_pool(self, input: TransformRequestInput) -> None:
        await workflow.start_child_workflow(
            PoolManagerWorkflow.run,
            PoolInput(
                spec=PoolSpec(
                    request_id=input.request_id,
                    image=input.image,
                    generated_code_cm=input.generated_code_cm,
                    transformer_language=input.transformer_language,
                    transformer_command=input.transformer_command,
                    result_destination=input.result_destination,
                    result_format=input.result_format,
                ),
                max_workers=input.max_workers,
                reconcile_seconds=self._tuning.pool_reconcile_seconds,
            ),
            id=pool_workflow_id(input.request_id),
            # Survive our continue-as-new; we cancel it ourselves when done.
            parent_close_policy=ParentClosePolicy.ABANDON,
        )
        self._state.pool_started = True

    async def _send_backlog(self, input: TransformRequestInput) -> None:
        s = self._state
        if not s.pool_started:
            return
        s.backlog_seq += 1
        outstanding = s.files_dispatched - s.files_completed - s.files_failed
        await signal_workflow(
            pool_workflow_id(input.request_id), "backlog", outstanding, s.backlog_seq
        )

    async def _stop_pool(self, input: TransformRequestInput) -> None:
        if not self._state.pool_started:
            return
        try:
            await workflow.get_external_workflow_handle(
                pool_workflow_id(input.request_id)
            ).cancel()
        except FailureError as err:  # the pool already ended
            workflow.logger.info("Could not cancel pool: %s", err)

    def _final_status(self) -> tuple[str, Optional[str]]:
        lookup = self._state.lookup_status
        if lookup == LOOKUP_COMPLETE:
            return REQUEST_COMPLETE, None
        if lookup in (LOOKUP_DOES_NOT_EXIST, LOOKUP_BAD_NAME):
            return REQUEST_BAD_DATASET, f"dataset lookup failed: {lookup}"
        return REQUEST_FATAL, f"dataset lookup failed: {lookup}"
