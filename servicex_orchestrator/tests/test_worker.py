import uuid

from temporalio.testing import WorkflowEnvironment

from fakes import FakeDatabase

from servicex_orchestrator.config import Settings
from servicex_orchestrator.models import REQUEST_COMPLETE, TransformRequestInput
from servicex_orchestrator.worker import build_worker, build_workers, connect, running
from servicex_orchestrator.workflows import PingWorkflow, TransformRequestWorkflow


def _settings(env: WorkflowEnvironment, **kwargs) -> Settings:
    return Settings(
        temporal_address=env.client.service_client.config.target_host,
        temporal_namespace=env.client.namespace,
        task_queue=f"test-{uuid.uuid4()}",
        log_level="INFO",
        **kwargs,
    )


async def test_ping_workflow_runs_on_worker():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        settings = _settings(env)
        async with build_worker(
            env.client, settings, db_activities=FakeDatabase().all()
        ):
            result = await env.client.execute_workflow(
                PingWorkflow.run,
                "hello",
                id=f"ping-{uuid.uuid4()}",
                task_queue=settings.task_queue,
            )
    assert result.startswith("pong from ")
    assert result.endswith(": hello")


async def test_connect_returns_client_once_namespace_exists():
    async with await WorkflowEnvironment.start_local() as env:
        client = await connect(_settings(env))
        assert client.namespace == env.client.namespace


async def test_stub_did_finders_serve_lookups():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        settings = _settings(
            env,
            stub_dataset_files=3,
            stub_activity_delay_seconds=0.0,
            stub_did_finder_schemes=("rucio", "cernopendata"),
        )
        workers = build_workers(
            env.client, settings, db_activities=FakeDatabase().all()
        )
        assert [w.task_queue for w in workers] == [
            settings.task_queue,
            "did-finder-rucio",
            "did-finder-cernopendata",
        ]
        request_id = str(uuid.uuid4())
        async with running(workers):
            result = await env.client.execute_workflow(
                TransformRequestWorkflow.run,
                TransformRequestInput(
                    request_id=request_id,
                    did="mc23:some.dataset",
                    did_scheme="rucio",
                    dataset_id=1,
                    image="img",
                    generated_code_cm="cm",
                    transformer_language="python",
                    transformer_command="cmd",
                    result_destination="object-store",
                    result_format="parquet",
                    max_workers=2,
                ),
                id=f"transform-{request_id}",
                task_queue=settings.task_queue,
            )
    assert result.status == REQUEST_COMPLETE
    assert result.files_completed == 3
