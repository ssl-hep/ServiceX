"""Stand-ins for the activities with a side effect that aren't real yet.

The dataset and request bookkeeping activities are real (`datasets.py`,
`request_status.py`, `files.py`). Each stub here
logs what the real activity would do and returns plausible fake data, so the workflows
can run end to end before the Kubernetes, object-store, DID-finder and
transform-worker pieces exist. Replace them one by one; keep the names and
signatures, since the workflows call them by name. `StubPoolBackend` stands in for
the WorkerBackend when WORKER_BACKEND=stub.

The fake dataset has `stub_files` files with ids 1..stub_files, whatever the DID.
"""

import asyncio
import hashlib
import time

from temporalio import activity
from temporalio.exceptions import WorkflowAlreadyStartedError

from servicex_orchestrator.backends.base import pilot_job_name
from servicex_orchestrator.models import (
    FILE_SUCCESS,
    FileResult,
    LookupInput,
    LookupSummary,
    PoolSpec,
    StartLookupInput,
    TransformFileInput,
)

LOOKUP_WORKFLOW_TYPE = "DatasetLookupWorkflow"
LOOKUP_CHUNK = 10
# What the stub transform_file reports for every file
STUB_FILE_EVENTS = 10_000
STUB_FILE_BYTES = 1_000_000


def lookup_workflow_id(dataset_id: int) -> str:
    """One lookup per dataset row, not per DID: a request for a DID whose old row went
    stale gets a new row, and must not join the old row's lookup."""
    return f"dataset-{dataset_id}"


def output_object_name(file_key: str, result_format: str) -> str:
    """Output names come from the file's identity, not the replica (plan §6.2)."""
    suffix = ".parquet" if result_format == "parquet" else ".root"
    return hashlib.sha256(file_key.encode()).hexdigest()[:40] + suffix


class StubActivities:
    def __init__(self, stub_files: int = 25, stub_delay: float = 0.5):
        self.stub_files = stub_files
        self.stub_delay = stub_delay

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

    # ----- transform worker ------------------------------------------------------

    @activity.defn
    async def transform_file(self, input: TransformFileInput) -> FileResult:
        replica = input.file.replicas[0]
        started = time.monotonic()
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
            events=STUB_FILE_EVENTS,
            bytes=STUB_FILE_BYTES,
            transform_seconds=time.monotonic() - started,
        )

    def all(self) -> list:
        """The activities the orchestrator's own queue serves."""
        return [
            self.start_dataset_lookup,
            self.transform_file,
        ]

    def did_finder(self) -> list:
        """What a stub DID-finder worker on `did-finder-<scheme>` serves."""
        return [self.lookup_dataset]


class StubPoolBackend:
    """A WorkerBackend that only logs, for setups without real pilots.

    It counts the pilots it "launched" per request in process memory, so
    count_live_pilots has something to report: fine with one orchestrator replica.
    Stub pilots never exit, so the pool tops up once and then holds.
    """

    def __init__(self) -> None:
        self._live_pilots: dict[str, int] = {}

    async def count_live_pilots(self, request_id: str) -> int:
        live = self._live_pilots.get(request_id, 0)
        activity.logger.info(
            "STUB count_live_pilots: would count Jobs labelled "
            "servicex/request-id=%s that are not Complete/Failed: %d",
            request_id,
            live,
        )
        return live

    async def launch_pilots(self, spec: PoolSpec, count: int, generation: int) -> None:
        names = [pilot_job_name(spec.request_id, generation, i) for i in range(count)]
        activity.logger.info(
            "STUB launch_pilots: would create Jobs %s running %s "
            "(AlreadyExists counts as success)",
            names,
            spec.image,
        )
        self._live_pilots[spec.request_id] = (
            self._live_pilots.get(spec.request_id, 0) + count
        )

    async def delete_pool(self, request_id: str) -> None:
        activity.logger.info(
            "STUB delete_pool: would delete every Job labelled "
            "servicex/request-id=%s (propagation Background)",
            request_id,
        )
        self._live_pilots.pop(request_id, None)

    async def cleanup_request(self, request_id: str) -> None:
        activity.logger.info(
            "STUB cleanup_request: would delete the ConfigMap and leftover "
            "transformer Jobs of request %s",
            request_id,
        )
        self._live_pilots.pop(request_id, None)
