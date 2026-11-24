"""Requests and their dataset lookup on the time-skipping test server, with the real
dataset and request activities on a real Postgres.

The DID finder is a fake `lookup_dataset` that writes files the way the app's PUT
endpoint does (an upsert on file_key) and signals progress like DIDFinderWorker.
Transforms are still the stubs.
"""

import contextlib
import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from pg_seed import NEEDS_DB
from servicex_orchestrator.activities import (
    StubActivities,
    build_db_activities,
    ping,
)
from servicex_orchestrator.config import did_finder_task_queue
from servicex_orchestrator.models import (
    DATASET_NOT_FOUND,
    LOOKUP_COMPLETE,
    LOOKUP_DOES_NOT_EXIST,
    REQUEST_BAD_DATASET,
    REQUEST_COMPLETE,
    LookupInput,
    LookupSummary,
    TransformRequestInput,
    TransformRequestTuning,
)
from servicex_orchestrator.workflows import WORKFLOWS, TransformRequestWorkflow

pytestmark = NEEDS_DB

FILE_SIZE = 1000
FILE_EVENTS = 10


class FakeFinder:
    """Writes `n_files` files in chunks, signalling the high-water mark after each."""

    def __init__(self, seed, n_files, chunk=4, fail_once_after=None, error=None):
        self.seed = seed
        self.n_files = n_files
        self.chunk = chunk
        self.fail_once_after = fail_once_after
        self.error = error
        self.attempts = 0

    @activity.defn(name="lookup_dataset")
    async def lookup_dataset(self, input: LookupInput) -> LookupSummary:
        self.attempts += 1
        if self.error:
            raise self.error
        keys = [f"scope:file-{i}" for i in range(self.n_files)]
        lookup = activity.client().get_workflow_handle(activity.info().workflow_id)
        hwm = 0
        for start in range(0, len(keys), self.chunk):
            written = start + self.chunk
            ids = await self.seed.files(
                input.dataset_id,
                keys[start:written],
                size=FILE_SIZE,
                events=FILE_EVENTS,
            )
            hwm = max(hwm, *ids)
            await lookup.signal("progress", hwm)
            if (
                self.fail_once_after is not None
                and activity.info().attempt == 1
                and written >= self.fail_once_after
            ):
                raise RuntimeError("transient Rucio error")
        return LookupSummary(
            n_files=len(keys),
            max_file_id=hwm,
            size_bytes=len(keys) * FILE_SIZE,
            events=len(keys) * FILE_EVENTS,
        )


@pytest.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@contextlib.asynccontextmanager
async def _workers(env, orchestrator, finder):
    task_queue = f"test-{uuid.uuid4()}"
    stubs = StubActivities(stub_files=0, stub_delay=0.0)
    workers = [
        Worker(
            env.client,
            task_queue=task_queue,
            workflows=WORKFLOWS,
            activities=[ping, *build_db_activities(orchestrator), *stubs.all()],
        ),
        Worker(
            env.client,
            task_queue=did_finder_task_queue("rucio"),
            activities=[finder.lookup_dataset],
        ),
    ]
    async with contextlib.AsyncExitStack() as stack:
        for worker in workers:
            await stack.enter_async_context(worker)
        yield task_queue


async def _submit(seed, dataset_id, status="lookup"):
    """What the app's submit leaves behind: a request row on the dataset row."""
    return await seed.request(dataset_id, status=status)


async def _run(env, task_queue, request_id, dataset_id):
    return await env.client.execute_workflow(
        TransformRequestWorkflow.run,
        TransformRequestInput(
            request_id=request_id,
            did="rucio://scope:some.dataset",
            did_scheme="rucio",
            dataset_id=dataset_id,
            image="img",
            generated_code_cm="cm",
            transformer_language="python",
            transformer_command="cmd",
            result_destination="object-store",
            result_format="parquet",
            max_workers=2,
            tuning=TransformRequestTuning(batch_size=50, pool_reconcile_seconds=1),
        ),
        id=f"transform-{request_id}",
        task_queue=task_queue,
    )


async def _dataset(seed, dataset_id):
    return await seed.row(
        "SELECT d.lookup_status, d.n_files, d.size, d.events, "
        "(SELECT count(*) FROM files f WHERE f.dataset_id = d.id) AS rows, "
        "(SELECT count(DISTINCT file_key) FROM files f WHERE f.dataset_id = d.id) "
        "AS keys FROM datasets d WHERE d.id = :d",
        d=dataset_id,
    )


async def _request(seed, request_id):
    return await seed.row(
        "SELECT status, files, workflow_id FROM requests WHERE request_id = :r",
        r=request_id,
    )


async def test_lookup_completes_the_dataset_and_runs_the_request(
    env, orchestrator, seed
):
    dataset_id = await seed.dataset("looking")
    finder = FakeFinder(seed, n_files=10)
    request_id = await _submit(seed, dataset_id)
    async with _workers(env, orchestrator, finder) as task_queue:
        result = await _run(env, task_queue, request_id, dataset_id)

    assert result.status == REQUEST_COMPLETE
    dataset = await _dataset(seed, dataset_id)
    assert tuple(dataset) == (
        LOOKUP_COMPLETE,
        10,
        10 * FILE_SIZE,
        10 * FILE_EVENTS,
        10,
        10,
    )
    request = await _request(seed, request_id)
    assert tuple(request) == ("running", 10, f"transform-{request_id}")


async def test_dataset_not_found(env, orchestrator, seed):
    dataset_id = await seed.dataset("looking")
    finder = FakeFinder(
        seed,
        n_files=0,
        error=ApplicationError(
            "no such DID", type=DATASET_NOT_FOUND, non_retryable=True
        ),
    )
    request_id = await _submit(seed, dataset_id)
    async with _workers(env, orchestrator, finder) as task_queue:
        result = await _run(env, task_queue, request_id, dataset_id)

    assert result.status == REQUEST_BAD_DATASET
    assert finder.attempts == 1
    assert (await _dataset(seed, dataset_id)).lookup_status == LOOKUP_DOES_NOT_EXIST
    # Never ran; finalize_request (still a stub) will record bad_dataset.
    assert (await _request(seed, request_id)).status == "lookup"


async def test_retried_lookup_leaves_no_duplicate_files(env, orchestrator, seed):
    dataset_id = await seed.dataset("looking")
    finder = FakeFinder(seed, n_files=12, fail_once_after=6)
    request_id = await _submit(seed, dataset_id)
    async with _workers(env, orchestrator, finder) as task_queue:
        result = await _run(env, task_queue, request_id, dataset_id)

    assert result.status == REQUEST_COMPLETE
    assert finder.attempts == 2
    dataset = await _dataset(seed, dataset_id)
    assert tuple(dataset) == (
        LOOKUP_COMPLETE,
        12,
        12 * FILE_SIZE,
        12 * FILE_EVENTS,
        12,
        12,
    )
    assert tuple(await _request(seed, request_id))[:2] == ("running", 12)


async def test_second_request_for_a_complete_dataset_skips_the_lookup(
    env, orchestrator, seed
):
    dataset_id = await seed.dataset("looking")
    finder = FakeFinder(seed, n_files=5)
    first = await _submit(seed, dataset_id)
    async with _workers(env, orchestrator, finder) as task_queue:
        await _run(env, task_queue, first, dataset_id)
        # Submit sees the dataset complete and marks the request running itself.
        second = await _submit(seed, dataset_id, status="running")
        result = await _run(env, task_queue, second, dataset_id)

    assert result.status == REQUEST_COMPLETE
    assert finder.attempts == 1
    assert tuple(await _request(seed, second))[:2] == ("running", 5)
    assert (await _dataset(seed, dataset_id)).rows == 5
