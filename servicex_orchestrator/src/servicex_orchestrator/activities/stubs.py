"""Stand-ins for the activities with a side effect that aren't real yet.

The dataset activities are real (`datasets.py`, `request_status.py`). Each stub here
logs what the real activity would do and returns plausible fake data, so the workflows
can run end to end before the Kubernetes, object-store, DID-finder and
transform-worker pieces exist. Replace them one by one; keep the names and
signatures, since the workflows call them by name.

The fake dataset has `stub_files` files with ids 1..stub_files, whatever the DID.
"""

import asyncio
import hashlib

from temporalio import activity
from temporalio.exceptions import WorkflowAlreadyStartedError

from servicex_orchestrator.models import (
    FILE_SUCCESS,
    ClaimBatchInput,
    FileRef,
    FileResult,
    FinalizeInput,
    LaunchPilotsInput,
    LookupInput,
    LookupSummary,
    PoolSpec,
    RecordFileResultInput,
    StartLookupInput,
    TransformFileInput,
)

LOOKUP_WORKFLOW_TYPE = "DatasetLookupWorkflow"
LOOKUP_CHUNK = 10


def lookup_workflow_id(dataset_id: int) -> str:
    """One lookup per dataset row, not per DID: a request for a DID whose old row went
    stale gets a new row, and must not join the old row's lookup."""
    return f"dataset-{dataset_id}"


def pilot_job_name(request_id: str, generation: int, index: int) -> str:
    return f"transformer-{request_id}-{generation}-{index}"


def output_object_name(file_key: str, result_format: str) -> str:
    """Output names come from the file's identity, not the replica (plan §6.2)."""
    suffix = ".parquet" if result_format == "parquet" else ".root"
    return hashlib.sha256(file_key.encode()).hexdigest()[:40] + suffix


class StubActivities:
    def __init__(self, stub_files: int = 25, stub_delay: float = 0.5):
        self.stub_files = stub_files
        self.stub_delay = stub_delay
        # Pilots "launched" per request, so count_live_pilots has something to report.
        # Process memory only: fine for a stub with one orchestrator replica.
        self._live_pilots: dict[str, int] = {}

    # ----- dataset lookup -------------------------------------------------------

    @activity.defn
    async def start_dataset_lookup(self, input: StartLookupInput) -> None:
        """Start the shared lookup, or join the one already running, and subscribe.

        Not a stub: signal-with-start on a deterministic workflow id is what makes N
        concurrent requests for one DID share a single lookup (plan §4.1 step 3).
        """
        workflow_id = lookup_workflow_id(input.lookup.dataset_id)
        activity.logger.info(
            "Subscribing %s to dataset lookup %s",
            input.subscriber_workflow_id,
            workflow_id,
        )
        client = activity.client()
        try:
            await client.start_workflow(
                LOOKUP_WORKFLOW_TYPE,
                input.lookup,
                id=workflow_id,
                task_queue=activity.info().task_queue,
                start_signal="subscribe",
                start_signal_args=[input.subscriber_workflow_id],
            )
        except WorkflowAlreadyStartedError:
            # A real server signals the running lookup instead of raising this, but
            # the time-skipping test server raises it. If the lookup closes before
            # this signal lands, the signal fails and the activity retry starts over.
            await client.get_workflow_handle(workflow_id).signal(
                "subscribe", input.subscriber_workflow_id
            )

    # ----- DID finder ------------------------------------------------------------

    @activity.defn
    async def lookup_dataset(self, input: LookupInput) -> LookupSummary:
        """Pretend to be a DID finder streaming replicas into the dataset cache."""
        info = activity.info()
        lookup = activity.client().get_workflow_handle(info.workflow_id)
        written = 0
        while written < self.stub_files:
            chunk = min(LOOKUP_CHUNK, self.stub_files - written)
            await asyncio.sleep(self.stub_delay)
            activity.logger.info(
                "STUB lookup_dataset: would upsert files %d..%d of %s://%s "
                "into dataset %s",
                written + 1,
                written + chunk,
                input.did_scheme,
                input.did,
                input.dataset_id,
                extra={"dataset_id": input.dataset_id},
            )
            written += chunk
            activity.heartbeat({"files_written": written})
            await lookup.signal("progress", written)
        return LookupSummary(
            n_files=written,
            max_file_id=written,
            size_bytes=written * 1_000_000,
            events=written * 10_000,
        )

    # ----- request bookkeeping ---------------------------------------------------

    @activity.defn
    async def claim_file_batch(self, input: ClaimBatchInput) -> list[FileRef]:
        last = min(input.after + input.limit, input.up_to)
        files = [
            FileRef(
                file_id=file_id,
                file_key=f"stub:dataset-{input.dataset_id}/file-{file_id}.root",
                replicas=[
                    f"root://stub-se-1//dataset-{input.dataset_id}/file-{file_id}.root"
                ],
            )
            for file_id in range(input.after + 1, last + 1)
        ]
        activity.logger.info(
            "STUB claim_file_batch: would select files of dataset %s with "
            "%d < id <= %d (limit %d) for request %s: got %d",
            input.dataset_id,
            input.after,
            input.up_to,
            input.limit,
            input.request_id,
            len(files),
        )
        return files

    @activity.defn
    async def record_file_result(self, input: RecordFileResultInput) -> None:
        r = input.result
        activity.logger.info(
            "STUB record_file_result: would upsert transform_result "
            "(file %s, request %s) = %s and update the request counters",
            r.file_id,
            input.request_id,
            r.status,
        )

    @activity.defn
    async def finalize_request(self, input: FinalizeInput) -> None:
        activity.logger.info(
            "STUB finalize_request: would set request %s to %r "
            "(%d files completed, %d failed)%s",
            input.request_id,
            input.status,
            input.files_completed,
            input.files_failed,
            f": {input.message}" if input.message else "",
        )

    @activity.defn
    async def cleanup_request(self, request_id: str) -> None:
        activity.logger.info(
            "STUB cleanup_request: would delete ConfigMap, leftover transformer "
            "Jobs and temp secrets of request %s",
            request_id,
        )

    # ----- transform worker ------------------------------------------------------

    @activity.defn
    async def transform_file(self, input: TransformFileInput) -> FileResult:
        replica = input.file.replicas[0]
        activity.heartbeat()
        await asyncio.sleep(self.stub_delay)
        object_name = output_object_name(input.file.file_key, input.spec.result_format)
        activity.logger.info(
            "STUB transform_file: would transform %s for request %s and write "
            "%s to %s",
            replica,
            input.spec.request_id,
            object_name,
            input.spec.result_destination,
        )
        return FileResult(
            file_id=input.file.file_id,
            status=FILE_SUCCESS,
            object_name=object_name,
            replica_used=replica,
            events=10_000,
            bytes=1_000_000,
        )

    # ----- worker pool -----------------------------------------------------------

    @activity.defn
    async def count_live_pilots(self, request_id: str) -> int:
        live = self._live_pilots.get(request_id, 0)
        activity.logger.info(
            "STUB count_live_pilots: would count Jobs labelled "
            "servicex/request-id=%s that are not Complete/Failed: %d",
            request_id,
            live,
        )
        return live

    @activity.defn
    async def launch_pilots(self, input: LaunchPilotsInput) -> None:
        names = [
            pilot_job_name(input.spec.request_id, input.generation, i)
            for i in range(input.count)
        ]
        activity.logger.info(
            "STUB launch_pilots: would create Jobs %s running %s "
            "(AlreadyExists counts as success)",
            names,
            input.spec.image,
        )
        self._live_pilots[input.spec.request_id] = (
            self._live_pilots.get(input.spec.request_id, 0) + input.count
        )

    @activity.defn
    async def delete_pool(self, spec: PoolSpec) -> None:
        activity.logger.info(
            "STUB delete_pool: would delete every Job labelled "
            "servicex/request-id=%s (propagation Background)",
            spec.request_id,
        )
        self._live_pilots.pop(spec.request_id, None)

    def all(self) -> list:
        """The activities the orchestrator's own queue serves."""
        return [
            self.start_dataset_lookup,
            self.claim_file_batch,
            self.record_file_result,
            self.finalize_request,
            self.cleanup_request,
            self.transform_file,
            self.count_live_pilots,
            self.launch_pilots,
            self.delete_pool,
        ]

    def did_finder(self) -> list:
        """What a stub DID-finder worker on `did-finder-<scheme>` serves."""
        return [self.lookup_dataset]
