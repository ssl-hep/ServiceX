"""The worker-pool activities, on whichever WorkerBackend this orchestrator runs.

The workflows call these by name (PoolManagerWorkflow: count_live_pilots,
launch_pilots, delete_pool; TransformRequestWorkflow: cleanup_request), so keep the
names and signatures.
"""

from temporalio import activity

from servicex_orchestrator.backends.base import WorkerBackend
from servicex_orchestrator.models import LaunchPilotsInput, PoolSpec


class PoolActivities:
    def __init__(self, backend: WorkerBackend):
        self.backend = backend

    @activity.defn
    async def count_live_pilots(self, request_id: str) -> int:
        return await self.backend.count_live_pilots(request_id)

    @activity.defn
    async def launch_pilots(self, input: LaunchPilotsInput) -> None:
        activity.logger.info(
            "Launching %d pilots (generation %d) running %s",
            input.count,
            input.generation,
            input.spec.image,
        )
        await self.backend.launch_pilots(input.spec, input.count, input.generation)

    @activity.defn
    async def delete_pool(self, spec: PoolSpec) -> None:
        activity.logger.info("Deleting the pilots of %s", spec.request_id)
        await self.backend.delete_pool(spec.request_id)

    @activity.defn
    async def cleanup_request(self, request_id: str) -> None:
        activity.logger.info("Cleaning up after request %s", request_id)
        await self.backend.cleanup_request(request_id)

    def all(self) -> list:
        return [
            self.count_live_pilots,
            self.launch_pilots,
            self.delete_pool,
            self.cleanup_request,
        ]
