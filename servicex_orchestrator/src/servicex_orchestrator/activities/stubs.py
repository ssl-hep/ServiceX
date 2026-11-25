"""Stand-ins for the activities with a side effect that aren't real yet.

The dataset and request bookkeeping activities are real (`datasets.py`,
`request_status.py`, `files.py`). Each stub here
logs what the real activity would do and returns plausible fake data, so the workflows
can run end to end before the Kubernetes, object-store, DID-finder and
transform-worker pieces exist. Replace them one by one; keep the names and
signatures, since the workflows call them by name. `StubPoolBackend` stands in for
the WorkerBackend when WORKER_BACKEND=stub: in place of pilot Jobs it runs a stub pilot
in this process, which serves the stub `transform_file` on the request's
`transform-<request_id>` queue, where FileBatchWorkflow schedules it.

The fake dataset has `stub_files` files with ids 1..stub_files, whatever the DID.
"""

import asyncio
import hashlib
import logging
import time
from datetime import timedelta
from typing import Optional

from temporalio import activity
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

from servicex_orchestrator.backends.base import pilot_job_name
from servicex_orchestrator.config import transform_task_queue
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

logger = logging.getLogger(__name__)


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
    # Served by StubPoolBackend's in-process pilot on `transform-<request_id>`, as
    # the transformer sidecar serves the real one.

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
        return [self.start_dataset_lookup]

    def did_finder(self) -> list:
        """What a stub DID-finder worker on `did-finder-<scheme>` serves."""
        return [self.lookup_dataset]


class StubPoolBackend:
    """A WorkerBackend for setups without real pilots.

    In place of the pilot Jobs, the first launch for a request starts one stub pilot
    in this process: a Temporal worker on `transform-<request_id>` serving the stub
    `transform_file` of `stubs`. delete_pool and cleanup_request shut it down.

    It counts the pilots it "launched" per request in process memory, so
    count_live_pilots has something to report: fine with one orchestrator replica.
    Stub pilots never exit by themselves, so the pool tops up once and then holds.
    """

    def __init__(self, stubs: Optional[StubActivities] = None) -> None:
        self.stubs = stubs or StubActivities()
        self._live_pilots: dict[str, int] = {}
        self._pilots: dict[str, Worker] = {}

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
        if spec.request_id not in self._pilots:
            self._start_pilot(spec.request_id)

    async def delete_pool(self, request_id: str) -> None:
        activity.logger.info(
            "STUB delete_pool: would delete every Job labelled "
            "servicex/request-id=%s (propagation Background)",
            request_id,
        )
        self._live_pilots.pop(request_id, None)
        await self._stop_pilot(request_id)

    async def cleanup_request(self, request_id: str) -> None:
        activity.logger.info(
            "STUB cleanup_request: would delete the ConfigMap and leftover "
            "transformer Jobs of request %s",
            request_id,
        )
        self._live_pilots.pop(request_id, None)
        await self._stop_pilot(request_id)

    async def close(self) -> None:
        """Stop every stub pilot, when the orchestrator shuts down."""
        await asyncio.gather(*(self._stop_pilot(r) for r in list(self._pilots)))

    def _start_pilot(self, request_id: str) -> None:
        task_queue = transform_task_queue(request_id)
        worker = Worker(
            activity.client(),
            task_queue=task_queue,
            activities=[self.stubs.transform_file],
            graceful_shutdown_timeout=timedelta(seconds=5),
        )
        self._pilots[request_id] = worker
        # Outlives this activity: it runs on the orchestrator's event loop until
        # delete_pool, cleanup_request or close stops it.
        task = asyncio.create_task(worker.run(), name=f"stub-pilot-{request_id}")
        task.add_done_callback(_log_pilot_exit)
        activity.logger.info("STUB pilot polling %s in this process", task_queue)

    async def _stop_pilot(self, request_id: str) -> None:
        worker = self._pilots.pop(request_id, None)
        if worker is not None:
            await worker.shutdown()


def _log_pilot_exit(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error("Stub pilot %s failed", task.get_name(), exc_info=task.exception())
