import asyncio
import contextlib
import dataclasses
import uuid
from collections import defaultdict

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from fakes import FakeDatabase
from servicex_orchestrator.activities import (
    PoolActivities,
    StubActivities,
    StubPoolBackend,
    ping,
)
from servicex_orchestrator.activities.stubs import STUB_FILE_BYTES, STUB_FILE_EVENTS
from servicex_orchestrator.config import did_finder_task_queue
from servicex_orchestrator.models import (
    DATASET_NOT_FOUND,
    LOOKUP_COMPLETE,
    LOOKUP_DOES_NOT_EXIST,
    REQUEST_BAD_DATASET,
    REQUEST_CANCELED,
    REQUEST_COMPLETE,
    REQUEST_FATAL,
    LaunchPilotsInput,
    LookupInput,
    LookupSummary,
    MarkRequestRunningInput,
    PoolInput,
    PoolSpec,
    PoolState,
    TransformRequestInput,
    TransformRequestState,
    TransformRequestTuning,
)
from servicex_orchestrator.workflows import (
    WORKFLOWS,
    PoolManagerWorkflow,
    TransformRequestWorkflow,
)


class RecordingPool(PoolActivities):
    """The pool activities on the stub backend, recording their inputs."""

    def __init__(self, calls: dict[str, list]):
        super().__init__(StubPoolBackend())
        self.calls = calls

    @activity.defn
    async def cleanup_request(self, request_id: str) -> None:
        self.calls["cleanup_request"].append(request_id)
        await super().cleanup_request(request_id)

    @activity.defn
    async def launch_pilots(self, input: LaunchPilotsInput) -> None:
        self.calls["launch_pilots"].append(input)
        await super().launch_pilots(input)

    @activity.defn
    async def delete_pool(self, spec: PoolSpec) -> None:
        self.calls["delete_pool"].append(spec)
        await super().delete_pool(spec)


class RecordingStubs(StubActivities):
    """The stubs, the stub pool and an in-memory dataset DB, plus a record of the
    calls the tests care about (the DB's calls included)."""

    def __init__(self, stub_files=23, stub_delay=0.0, lookup_error=None):
        super().__init__(stub_files=stub_files, stub_delay=stub_delay)
        self.lookup_error = lookup_error
        self.calls: dict[str, list] = defaultdict(list)
        self.db = FakeDatabase(self.calls)
        self.pool = RecordingPool(self.calls)

    def all(self) -> list:
        return [*self.db.all(), *super().all(), *self.pool.all()]

    @activity.defn
    async def lookup_dataset(self, input: LookupInput) -> LookupSummary:
        self.calls["lookup_dataset"].append(input)
        self.calls["lookup_task_queue"].append(activity.info().task_queue)
        if self.lookup_error:
            raise self.lookup_error
        return await super().lookup_dataset(input)


@pytest.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.fixture
async def local_env():
    """A real dev server, in real time.

    For tests that depend on signal-with-start or on cancellation landing during a
    timer: the time-skipping test server raises WorkflowAlreadyStarted on
    signal-with-start of a running workflow, and sometimes never dispatches the
    activity a workflow schedules right after it is canceled.
    """
    async with await WorkflowEnvironment.start_local() as env:
        yield env


@contextlib.asynccontextmanager
async def _workers(env, stubs: StubActivities, did_schemes=("rucio",)):
    """The orchestrator worker plus a stub DID finder per scheme; yields its queue.

    Each test gets its own server, so the fixed `did-finder-<scheme>` queues are
    not shared between tests.
    """
    task_queue = f"test-{uuid.uuid4()}"
    orchestrator = Worker(
        env.client,
        task_queue=task_queue,
        workflows=WORKFLOWS,
        activities=[ping, *stubs.all()],
    )
    did_finders = [
        Worker(
            env.client,
            task_queue=did_finder_task_queue(scheme),
            activities=stubs.did_finder(),
        )
        for scheme in did_schemes
    ]
    async with contextlib.AsyncExitStack() as stack:
        for worker in [orchestrator, *did_finders]:
            await stack.enter_async_context(worker)
        yield task_queue


SMALL = TransformRequestTuning(
    batch_size=5, max_concurrent_batches=2, batches_per_run=50, pool_reconcile_seconds=1
)


def _request(did="mc23:some.dataset", scheme="rucio", max_workers=3, tuning=None):
    return TransformRequestInput(
        request_id=str(uuid.uuid4()),
        did=did,
        did_scheme=scheme,
        dataset_id=42,
        image="sslhep/servicex_func_adl_xaod_transformer:develop",
        generated_code_cm="my-cm",
        transformer_language="python",
        transformer_command="transform_single_file.py",
        result_destination="object-store",
        result_format="parquet",
        max_workers=max_workers,
        tuning=tuning or SMALL,
    )


async def _run_request(env, task_queue, request):
    return await env.client.execute_workflow(
        TransformRequestWorkflow.run,
        request,
        id=f"transform-{request.request_id}",
        task_queue=task_queue,
    )


async def test_did_request_runs_end_to_end(env):
    stubs = RecordingStubs(stub_files=23)
    async with _workers(env, stubs) as task_queue:
        request = _request()
        result = await _run_request(env, task_queue, request)

    assert result.status == REQUEST_COMPLETE
    assert (result.files_completed, result.files_failed) == (23, 0)
    assert len(stubs.calls["lookup_dataset"]) == 1
    [final] = stubs.calls["finalize_request"]
    assert (final.status, final.files_completed, final.files_failed) == (
        REQUEST_COMPLETE,
        23,
        0,
    )
    assert (final.total_events, final.total_bytes) == (
        23 * STUB_FILE_EVENTS,
        23 * STUB_FILE_BYTES,
    )
    assert final.message is None
    # Every file recorded once, and the totals written after each batch of 5.
    assert sorted(f for _, f in stubs.db.results) == list(range(1, 24))
    progress = stubs.calls["record_request_progress"]
    assert len(progress) == 5
    assert {p.files_completed for p in progress} == {5, 10, 15, 20, 23}
    assert all(p.total_events == p.files_completed * STUB_FILE_EVENTS for p in progress)
    assert stubs.calls["cleanup_request"] == [request.request_id]
    assert stubs.calls["launch_pilots"], "the pool should have launched pilots"
    [recorded] = stubs.calls["record_request_workflow"]
    assert recorded.workflow_id == f"transform-{request.request_id}"
    assert stubs.calls["mark_request_running"] == [
        MarkRequestRunningInput(request.request_id, 23)
    ]


async def test_lookup_is_scheduled_on_the_did_finder_queue(env):
    """`lookup_dataset` goes to `did-finder-<scheme>`, not the orchestrator queue."""
    stubs = RecordingStubs(stub_files=4)
    async with _workers(env, stubs, did_schemes=("cernopendata",)) as task_queue:
        result = await _run_request(
            env, task_queue, _request(did="1507", scheme="cernopendata")
        )

    assert result.status == REQUEST_COMPLETE
    assert stubs.calls["lookup_task_queue"] == ["did-finder-cernopendata"]


async def test_request_accepts_app_payload_as_plain_dict(env):
    """The app sends the input as JSON with no state or tuning arguments."""
    stubs = RecordingStubs(stub_files=3)
    payload = dataclasses.asdict(_request())
    del payload["tuning"], payload["state"]
    async with _workers(env, stubs) as task_queue:
        result = await env.client.execute_workflow(
            "TransformRequestWorkflow",
            payload,
            id=f"transform-{payload['request_id']}",
            task_queue=task_queue,
        )
    assert result["status"] == REQUEST_COMPLETE
    assert result["files_completed"] == 3


async def test_file_list_request_skips_lookup(env):
    stubs = RecordingStubs(stub_files=7)
    # The app creates a file-list dataset complete, with its files.
    stubs.db.preset(42, LOOKUP_COMPLETE, n_files=7)
    async with _workers(env, stubs) as task_queue:
        request = _request(did="file-list-hash", scheme="user")
        result = await _run_request(env, task_queue, request)

    assert result.status == REQUEST_COMPLETE
    assert result.files_completed == 7
    assert stubs.calls["lookup_dataset"] == []
    assert stubs.calls["mark_request_running"] == [
        MarkRequestRunningInput(request.request_id, 7)
    ]


async def test_concurrent_requests_share_one_lookup(local_env):
    # A slow lookup, so the second request subscribes while it is still running.
    stubs = RecordingStubs(stub_files=30, stub_delay=0.2)
    async with _workers(local_env, stubs) as task_queue:
        first, second = _request(), _request()
        results = await asyncio.gather(
            _run_request(local_env, task_queue, first),
            _run_request(local_env, task_queue, second),
        )

    assert [r.files_completed for r in results] == [30, 30]
    assert len(stubs.calls["lookup_dataset"]) == 1


async def test_continue_as_new_keeps_counts(env):
    stubs = RecordingStubs(stub_files=23)
    tuning = TransformRequestTuning(
        batch_size=3, max_concurrent_batches=2, batches_per_run=2
    )
    request = _request(tuning=tuning)
    async with _workers(env, stubs) as task_queue:
        handle = await env.client.start_workflow(
            TransformRequestWorkflow.run,
            request,
            id=f"transform-{request.request_id}",
            task_queue=task_queue,
        )
        result = await handle.result()
        latest = await env.client.get_workflow_handle(handle.id).describe()

    assert (result.files_completed, result.files_failed) == (23, 0)
    assert latest.run_id != handle.first_execution_run_id
    # One pool for the whole request, despite several runs.
    assert {p.spec.request_id for p in stubs.calls["launch_pilots"]} == {
        request.request_id
    }


async def test_cancel_cleans_up(local_env):
    env = local_env
    stubs = RecordingStubs(stub_files=40, stub_delay=0.5)
    request = _request()
    async with _workers(env, stubs) as task_queue:
        handle = await env.client.start_workflow(
            TransformRequestWorkflow.run,
            request,
            id=f"transform-{request.request_id}",
            task_queue=task_queue,
        )
        for _ in range(100):
            status = await handle.query(TransformRequestWorkflow.status)
            if status.batches_in_flight:
                break
            await asyncio.sleep(0.1)
        assert status.batches_in_flight

        await handle.cancel()
        with pytest.raises(WorkflowFailureError) as err:
            await handle.result()
        assert isinstance(err.value.cause, CancelledError)

        pool = env.client.get_workflow_handle(f"pool-{request.request_id}")
        with pytest.raises(WorkflowFailureError):
            await pool.result()

    assert [f.status for f in stubs.calls["finalize_request"]] == [REQUEST_CANCELED]
    assert stubs.calls["cleanup_request"] == [request.request_id]
    assert [s.request_id for s in stubs.calls["delete_pool"]] == [request.request_id]


async def test_dataset_not_found_ends_bad_dataset(env):
    stubs = RecordingStubs(
        lookup_error=ApplicationError(
            "no such dataset", type=DATASET_NOT_FOUND, non_retryable=True
        )
    )
    async with _workers(env, stubs) as task_queue:
        result = await _run_request(env, task_queue, _request())

    assert result.status == REQUEST_BAD_DATASET
    assert len(stubs.calls["lookup_dataset"]) == 1
    [failed] = stubs.calls["mark_dataset_failed"]
    assert failed.status == LOOKUP_DOES_NOT_EXIST
    assert stubs.calls["launch_pilots"] == [], "no pods for a missing dataset"
    assert stubs.calls["cleanup_request"]
    assert stubs.calls["mark_request_running"] == []
    [final] = stubs.calls["finalize_request"]
    assert (final.status, final.files_completed, final.files_failed) == (
        REQUEST_BAD_DATASET,
        0,
        0,
    )
    assert final.message == "dataset lookup failed: does_not_exist"
    assert stubs.calls["record_request_progress"] == []


async def test_second_request_for_a_complete_dataset_starts_no_lookup(env):
    stubs = RecordingStubs(stub_files=6)
    async with _workers(env, stubs) as task_queue:
        first = await _run_request(env, task_queue, _request())
        second = await _run_request(env, task_queue, _request())

    assert [r.files_completed for r in (first, second)] == [6, 6]
    assert len(stubs.calls["lookup_dataset"]) == 1
    assert [m.files for m in stubs.calls["mark_request_running"]] == [6, 6]


async def test_lookup_of_a_complete_dataset_finishes_without_looking(env):
    """A request that saw `looking` just before the lookup finished starts a new
    lookup workflow; it must find the row complete and not run the DID finder."""
    stubs = RecordingStubs(stub_files=6)
    stubs.db.preset(42, LOOKUP_COMPLETE, n_files=6)
    async with _workers(env, stubs) as task_queue:
        status = await env.client.execute_workflow(
            "DatasetLookupWorkflow",
            LookupInput("hash", "mc23:some.dataset", "rucio", 42),
            id="dataset-42",
            task_queue=task_queue,
        )

    assert status == LOOKUP_COMPLETE
    assert stubs.calls["lookup_dataset"] == []
    assert stubs.calls["mark_dataset_looking"] == []


async def test_missing_dataset_row_ends_fatal(env):
    stubs = RecordingStubs()
    stubs.db.missing.add(42)
    async with _workers(env, stubs) as task_queue:
        result = await _run_request(env, task_queue, _request())

    assert result.status == REQUEST_FATAL
    assert stubs.calls["lookup_dataset"] == []
    [final] = stubs.calls["finalize_request"]
    assert "internal_failure" in final.message


async def test_pool_manager_tops_up_without_overshooting(local_env):
    env = local_env
    stubs = RecordingStubs()
    spec = PoolSpec("req-1", "img", "cm", "python", "cmd", "object-store", "parquet")
    async with _workers(env, stubs) as task_queue:
        handle = await env.client.start_workflow(
            PoolManagerWorkflow.run,
            PoolInput(spec=spec, max_workers=3, reconcile_seconds=0.2),
            id=f"pool-{uuid.uuid4()}",
            task_queue=task_queue,
        )

        async def outstanding():
            return (await handle.query(PoolManagerWorkflow.state)).outstanding

        await handle.signal(PoolManagerWorkflow.backlog, args=[10, 1])
        await asyncio.sleep(1.5)  # several reconciles
        assert [p.count for p in stubs.calls["launch_pilots"]] == [3]

        await handle.signal(PoolManagerWorkflow.backlog, args=[2, 2])
        await handle.signal(PoolManagerWorkflow.backlog, args=[50, 1])  # stale
        await asyncio.sleep(1.5)
        assert await outstanding() == 2
        assert len(stubs.calls["launch_pilots"]) == 1

        await handle.cancel()
        with pytest.raises(WorkflowFailureError):
            await handle.result()

    assert stubs.calls["delete_pool"] == [spec]


async def test_state_and_tuning_round_trip():
    """Continue-as-new state must survive JSON, including the defaults."""
    from temporalio.converter import DataConverter

    converter = DataConverter.default
    state = TransformRequestState(initialized=True, cursor=5, hwm=9)
    [payload] = await converter.encode([state])
    [decoded] = await converter.decode([payload], [TransformRequestState])
    assert decoded == state
    [payload] = await converter.encode([PoolState(3, 2, 1)])
    [decoded] = await converter.decode([payload], [PoolState])
    assert decoded == PoolState(3, 2, 1)
