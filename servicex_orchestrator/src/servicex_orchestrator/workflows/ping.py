from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from servicex_orchestrator.activities.health import ping


@workflow.defn
class PingWorkflow:
    """Smoke test: runs one activity on the orchestrator and returns its reply.

    Start it from the Temporal UI or with
    `temporal workflow execute --type PingWorkflow --task-queue servicex-orchestrator
    --input '"hello"'`.
    """

    @workflow.run
    async def run(self, message: str) -> str:
        return await workflow.execute_activity(
            ping,
            message,
            start_to_close_timeout=timedelta(seconds=30),
        )
