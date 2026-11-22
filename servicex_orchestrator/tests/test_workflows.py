import asyncio
import dataclasses
import uuid
from collections import defaultdict

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from servicex_orchestrator.activities import StubActivities, ping
from servicex_orchestrator.models import (
    DATASET_NOT_FOUND,
    LOOKUP_DOES_NOT_EXIST,
    REQUEST_BAD_DATASET,
    REQUEST_CANCELED,
    REQUEST_COMPLETE,
    FinalizeInput,
    LaunchPilotsInput,
    LookupInput,
    LookupSummary,
    MarkDatasetFailedInput,
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


class RecordingStubs(StubActivities):
    """The stubs, plus a record of the calls the tests care about."""

    def __init__(self, stub_files=23, stub_delay=0.0, lookup_error=None):
        super().__init__(stub_files=stub_files, stub_delay=stub_delay)
        self.lookup_error = lookup_error
        self.calls: dict[str, list] = defaultdict(list)

    @activity.defn
    async def lookup_dataset(self, input: LookupInput) -> LookupSummary:
        self.calls["lookup_dataset"].append(input)
        if self.lookup_error:
            raise self.lookup_error
        return await super().lookup_dataset(input)

    @activity.defn
    async def mark_dataset_failed(self, input: MarkDatasetFailedInput) -> None:
        self.calls["mark_dataset_failed"].append(input)
        await super().mark_dataset_failed(input)

    @activity.defn
    async def finalize_request(self, input: FinalizeInput) -> None:
        self.calls["finalize_request"].append(input)
        await super().finalize_request(input)

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


def _worker(env, stubs: StubActivities) -> tuple[Worker, str]:
    task_queue = f"test-{uuid.uuid4()}"
    worker = Worker(
        env.client,
        task_queue=task_queue,
        workflows=WORKFLOWS,
        activities=[ping, *stubs.all()],
    )
    return worker, task_queue


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
    worker, task_queue = _worker(env, stubs)
    async with worker:
        request = _request()
        result = await _run_request(env, task_queue, request)

    assert result.status == REQUEST_COMPLETE
    assert (result.files_completed, result.files_failed) == (23, 0)
    assert len(stubs.calls["lookup_dataset"]) == 1
    [final] = stubs.calls["finalize_request"]
    assert (final.status, final.files_completed) == (REQUEST_COMPLETE, 23)
    assert stubs.calls["cleanup_request"] == [request.request_id]
    assert stubs.calls["launch_pilots"], "the pool should have launched pilots"


async def test_request_accepts_app_payload_as_plain_dict(env):
    """The app sends the input as JSON with no state or tuning arguments."""
    stubs = RecordingStubs(stub_files=3)
    worker, task_queue = _worker(env, stubs)
    payload = dataclasses.asdict(_request())
    del payload["tuning"], payload["state"]
    async with worker:
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
    worker, task_queue = _worker(env, stubs)
    async with worker:
        result = await _run_request(
            env, task_queue, _request(did="file-list-hash", scheme="user")
        )

    assert result.status == REQUEST_COMPLETE
    assert result.files_completed == 7
    assert stubs.calls["lookup_dataset"] == []


async def test_concurrent_requests_share_one_lookup(local_env):
    # A slow lookup, so the second request subscribes while it is still running.
    stubs = RecordingStubs(stub_files=30, stub_delay=0.2)
    worker, task_queue = _worker(local_env, stubs)
    async with worker:
        first, second = _request(), _request()
        results = await asyncio.gather(
            _run_request(local_env, task_queue, first),
            _run_request(local_env, task_queue, second),
        )

    assert [r.files_completed for r in results] == [30, 30]
    assert len(stubs.calls["lookup_dataset"]) == 1


async def test_continue_as_new_keeps_counts(env):
    stubs = RecordingStubs(stub_files=23)
    worker, task_queue = _worker(env, stubs)
    tuning = TransformRequestTuning(
        batch_size=3, max_concurrent_batches=2, batches_per_run=2
    )
    request = _request(tuning=tuning)
    async with worker:
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
    worker, task_queue = _worker(env, stubs)
    request = _request()
    async with worker:
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
    worker, task_queue = _worker(env, stubs)
    async with worker:
        result = await _run_request(env, task_queue, _request())

    assert result.status == REQUEST_BAD_DATASET
    assert len(stubs.calls["lookup_dataset"]) == 1
    [failed] = stubs.calls["mark_dataset_failed"]
    assert failed.status == LOOKUP_DOES_NOT_EXIST
    assert stubs.calls["launch_pilots"] == [], "no pods for a missing dataset"
    assert stubs.calls["cleanup_request"]


async def test_pool_manager_tops_up_without_overshooting(local_env):
    env = local_env
    stubs = RecordingStubs()
    worker, task_queue = _worker(env, stubs)
    spec = PoolSpec("req-1", "img", "cm", "python", "cmd", "object-store", "parquet")
    async with worker:
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
