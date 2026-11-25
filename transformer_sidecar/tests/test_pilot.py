import asyncio
import json
import threading
import uuid
from datetime import timedelta

import pytest
from temporalio import workflow
from temporalio.client import WorkflowFailureError
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from transformer_sidecar import pilot as pilot_module
from transformer_sidecar.file_transformer import PublishError, TransformOutcome
from transformer_sidecar.pilot import (
    EXIT_BROKEN,
    EXIT_OK,
    Pilot,
    PilotSettings,
    TransformActivity,
    init_logging,
    start_transformer,
    stop_science_container,
)
from transformer_sidecar.science_container_command import ScienceContainerException
from transformer_sidecar.temporal_models import (
    FILE_FAILED,
    TRANSIENT_IO,
    FileRef,
    FileResult,
    TransformFileInput,
    TransformSpec,
)

REQUEST_ID = "req-1"
INPUT = TransformFileInput(
    spec=TransformSpec(REQUEST_ID, "object-store", "parquet"),
    file=FileRef(file_id=7, file_key="k", replicas=["root://a/f.root"]),
)
SUCCESS = TransformOutcome(
    success=True,
    replica_used="root://a/f.root",
    object_name="obj.parquet",
    events=10,
    bytes=20,
    seconds=1.5,
)


class FakeTransformer:
    """Returns (or raises) each of `results` in turn; waits on `release` if set."""

    def __init__(self, *results, release: threading.Event = None):
        self.request_id = REQUEST_ID
        self.results = list(results)
        self.release = release
        self.calls = []
        self.science_container = None

    def transform(self, file):
        self.calls.append(file)
        if self.release is not None:
            self.release.wait(10)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


# ----- the activity --------------------------------------------------------------


async def test_success_returns_file_result():
    transform = TransformActivity(FakeTransformer(SUCCESS))

    result = await ActivityEnvironment().run(transform.transform_file, INPUT)

    assert result == FileResult(
        file_id=7,
        status="success",
        object_name="obj.parquet",
        replica_used="root://a/f.root",
        events=10,
        bytes=20,
        transform_seconds=1.5,
    )
    assert transform.in_flight == 0
    assert not transform.broken.is_set()


async def test_every_replica_failed_is_non_retryable():
    failed = TransformOutcome(
        success=False,
        replica_used="root://a/f.root",
        error_info="Property naming error",
        log_body="x" * 100_000,
    )
    transform = TransformActivity(FakeTransformer(failed))

    with pytest.raises(ApplicationError) as err:
        await ActivityEnvironment().run(transform.transform_file, INPUT)

    assert err.value.type == FILE_FAILED
    assert err.value.non_retryable
    assert err.value.message == "Property naming error"
    [details] = err.value.details
    assert details["error_info"] == "Property naming error"
    assert details["replica"] == "root://a/f.root"
    assert len(details["log_body"]) == pilot_module.MAX_LOG_BODY_CHARS


async def test_publish_error_is_retryable():
    transform = TransformActivity(FakeTransformer(PublishError("minio down")))

    with pytest.raises(ApplicationError) as err:
        await ActivityEnvironment().run(transform.transform_file, INPUT)

    assert err.value.type == TRANSIENT_IO
    assert not err.value.non_retryable
    assert not transform.broken.is_set()


async def test_broken_science_container_is_retryable_and_breaks_the_pilot():
    transform = TransformActivity(FakeTransformer(ScienceContainerException("gone")))

    with pytest.raises(ApplicationError) as err:
        await ActivityEnvironment().run(transform.transform_file, INPUT)

    assert err.value.type == TRANSIENT_IO
    assert not err.value.non_retryable
    assert transform.broken.is_set()


async def test_unexpected_error_propagates():
    transform = TransformActivity(FakeTransformer(KeyError("stats-parser")))

    with pytest.raises(KeyError):
        await ActivityEnvironment().run(transform.transform_file, INPUT)
    assert transform.in_flight == 0


async def test_file_of_another_request_is_refused():
    transformer = FakeTransformer(SUCCESS)
    transform = TransformActivity(transformer)
    other = TransformFileInput(
        spec=TransformSpec("someone-else", "object-store", "parquet"), file=INPUT.file
    )

    with pytest.raises(ApplicationError) as err:
        await ActivityEnvironment().run(transform.transform_file, other)

    assert err.value.type == TRANSIENT_IO
    assert transformer.calls == []


async def test_heartbeats_while_transforming():
    release = threading.Event()
    transform = TransformActivity(
        FakeTransformer(SUCCESS, release=release), heartbeat_interval=0.01
    )
    env = ActivityEnvironment()
    heartbeats = []

    def on_heartbeat(*details):
        heartbeats.append(details)
        if len(heartbeats) >= 3:
            release.set()

    env.on_heartbeat = on_heartbeat

    result = await env.run(transform.transform_file, INPUT)

    assert result.status == "success"
    assert len(heartbeats) >= 3


# ----- the pilot -----------------------------------------------------------------


@workflow.defn(sandboxed=False)
class OneFileWorkflow:
    """Schedules transform_file on the request's queue, as FileBatchWorkflow does."""

    @workflow.run
    async def run(self, input: TransformFileInput) -> FileResult:
        return await workflow.execute_activity(
            "transform_file",
            input,
            result_type=FileResult,
            task_queue=f"transform-{input.spec.request_id}",
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


@pytest.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


def settings(**overrides) -> PilotSettings:
    values = dict(
        request_id=REQUEST_ID,
        result_destination="object-store",
        result_format="parquet",
        idle_timeout_seconds=60,
        graceful_shutdown_seconds=1,
    )
    values.update(overrides)
    return PilotSettings(**values)


async def run_one_file(env, workflow_queue="workflows"):
    async with Worker(
        env.client,
        task_queue=workflow_queue,
        workflows=[OneFileWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):
        return await env.client.execute_workflow(
            OneFileWorkflow.run,
            INPUT,
            id=f"one-file-{uuid.uuid4()}",
            task_queue=workflow_queue,
        )


async def test_pilot_polls_the_request_queue(env):
    pilot = Pilot(
        settings(), TransformActivity(FakeTransformer(SUCCESS)), poll_interval=0.05
    )
    assert pilot.settings.task_queue == f"transform-{REQUEST_ID}"
    stop = asyncio.Event()
    running = asyncio.create_task(pilot.run(env.client, stop))

    result = await run_one_file(env)

    assert result.object_name == "obj.parquet"
    assert not running.done()
    stop.set()
    assert await asyncio.wait_for(running, 10) == EXIT_OK


async def test_pilot_exits_when_idle(env):
    pilot = Pilot(
        settings(idle_timeout_seconds=0.2),
        TransformActivity(FakeTransformer()),
        poll_interval=0.05,
    )

    assert await asyncio.wait_for(pilot.run(env.client, asyncio.Event()), 10) == EXIT_OK


async def test_pilot_is_not_idle_while_transforming(env):
    release = threading.Event()
    transform = TransformActivity(FakeTransformer(SUCCESS, release=release))
    pilot = Pilot(settings(idle_timeout_seconds=0.2), transform, poll_interval=0.05)
    # Count idle time from the moment the file arrives, so the pilot waits for it
    transform.last_finished = float("inf")
    running = asyncio.create_task(pilot.run(env.client, asyncio.Event()))
    file_done = asyncio.create_task(run_one_file(env))

    while transform.in_flight == 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)  # well past the idle timeout
    assert not running.done()

    release.set()
    assert (await file_done).status == "success"
    assert await asyncio.wait_for(running, 10) == EXIT_OK


async def test_pilot_exits_broken_when_science_container_dies(env):
    transform = TransformActivity(FakeTransformer(ScienceContainerException("gone")))
    pilot = Pilot(settings(), transform, poll_interval=0.05)
    running = asyncio.create_task(pilot.run(env.client, asyncio.Event()))

    with pytest.raises(WorkflowFailureError) as err:
        await run_one_file(env)

    assert isinstance(err.value.cause, ActivityError)
    assert err.value.cause.cause.type == TRANSIENT_IO
    assert await asyncio.wait_for(running, 10) == EXIT_BROKEN


# ----- settings and startup --------------------------------------------------------


def test_settings_from_env():
    s = PilotSettings.from_env(
        {
            "REQUEST_ID": "r9",
            "RESULT_DESTINATION": "volume",
            "RESULT_FORMAT": "root-file",
            "TEMPORAL_ADDRESS": "temporal:7233",
            "TEMPORAL_NAMESPACE": "servicex",
            "SHARED_DIR": "/servicex/output",
            "OUTPUT_DIR": "/posix_volume/out",
            "WORKER_IDLE_TIMEOUT_SECONDS": "30",
        }
    )
    assert s.task_queue == "transform-r9"
    assert s.temporal_address == "temporal:7233"
    assert s.temporal_namespace == "servicex"
    assert s.output_dir == "/posix_volume/out"
    assert s.idle_timeout_seconds == 30
    assert s.graceful_shutdown_seconds == 25

    assert (
        PilotSettings.from_env(
            {
                "REQUEST_ID": "r9",
                "RESULT_DESTINATION": "volume",
                "RESULT_FORMAT": "root-file",
                "TEMPORAL_TASK_QUEUE": "custom",
            }
        ).task_queue
        == "custom"
    )


def test_settings_need_the_request():
    with pytest.raises(ValueError, match="REQUEST_ID"):
        PilotSettings.from_env({"RESULT_DESTINATION": "volume", "RESULT_FORMAT": "x"})


def test_start_transformer(tmp_path, mocker):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "transformer_capabilities.json").write_text(
        json.dumps({"file-formats": ["root-file"], "stats-parser": "UprootStats"})
    )
    store = mocker.patch("transformer_sidecar.pilot.ObjectStoreManager")
    science = mocker.patch("transformer_sidecar.pilot.ScienceContainerCommand")

    transformer = start_transformer(settings(shared_dir=str(shared)))

    assert (shared / "scripts" / "watch.sh").is_file()
    assert (shared / "scripts" / "proxy-exporter.sh").is_file()
    science.assert_called_once_with(request_id=REQUEST_ID)
    assert transformer.science_container is science.return_value
    assert transformer.object_store is store.return_value
    assert transformer.convert_to_parquet


def test_stop_science_container_tolerates_a_dead_socket(mocker):
    transformer = mocker.MagicMock()
    transformer.science_container.close.side_effect = BrokenPipeError()

    stop_science_container(transformer)

    transformer.science_container.close.assert_called_once()


def test_init_logging_prints_each_line_once(monkeypatch):
    import logging

    monkeypatch.delenv("VECTOR_HOST", raising=False)
    monkeypatch.delenv("LOGSTASH_HOST", raising=False)
    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        init_logging(REQUEST_ID)
        streams = [h for h in root.handlers if type(h) is logging.StreamHandler]
        assert len(streams) == 1
    finally:
        root.handlers[:] = saved
