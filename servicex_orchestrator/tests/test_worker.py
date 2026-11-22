import uuid

from temporalio.testing import WorkflowEnvironment

from servicex_orchestrator.config import Settings
from servicex_orchestrator.worker import build_worker, connect
from servicex_orchestrator.workflows import PingWorkflow


def _settings(env: WorkflowEnvironment) -> Settings:
    return Settings(
        temporal_address=env.client.service_client.config.target_host,
        temporal_namespace=env.client.namespace,
        task_queue=f"test-{uuid.uuid4()}",
        log_level="INFO",
    )


async def test_ping_workflow_runs_on_worker():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        settings = _settings(env)
        async with build_worker(env.client, settings):
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
