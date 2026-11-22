import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from servicex_orchestrator.models import (
        LaunchPilotsInput,
        PoolInput,
        PoolState,
    )
    from servicex_orchestrator.workflows.common import orchestrator_activity


@workflow.defn
class PoolManagerWorkflow:
    """Keeps enough transformer pilots running for a request's backlog (plan §4.4).

    Id `pool-<request_id>`. It only ever adds pilots; pilots exit on their own once
    the queue goes idle, so no pod is killed mid-file. The parent reports the backlog
    with `backlog(n, seq)`. When canceled it deletes every pilot of the request.
    """

    @workflow.init
    def __init__(self, input: PoolInput) -> None:
        self._outstanding = input.state.outstanding
        self._generation = input.state.generation
        self._backlog_seq = input.state.backlog_seq
        self._changed = False

    @workflow.signal
    def backlog(self, outstanding: int, seq: int) -> None:
        """Files dispatched but not finished. `seq` drops signals that arrive late."""
        if seq <= self._backlog_seq:
            return
        self._backlog_seq = seq
        self._outstanding = outstanding
        self._changed = True

    @workflow.query
    def state(self) -> PoolState:
        return PoolState(self._outstanding, self._generation, self._backlog_seq)

    @workflow.run
    async def run(self, input: PoolInput) -> None:
        request_id = input.spec.request_id
        try:
            for _ in range(input.max_iterations):
                await self._reconcile(input)
                self._changed = False
                try:
                    # Reconcile on a timer, and also as soon as the backlog changes.
                    await workflow.wait_condition(
                        lambda: self._changed,
                        timeout=timedelta(seconds=input.reconcile_seconds),
                    )
                except asyncio.TimeoutError:
                    pass
                if workflow.info().is_continue_as_new_suggested():
                    break
        except asyncio.CancelledError:
            workflow.logger.info("Pool for %s canceled, deleting pilots", request_id)
            await orchestrator_activity("delete_pool", input.spec)
            raise

        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(
            PoolInput(
                spec=input.spec,
                max_workers=input.max_workers,
                reconcile_seconds=input.reconcile_seconds,
                max_iterations=input.max_iterations,
                state=PoolState(self._outstanding, self._generation, self._backlog_seq),
            )
        )

    async def _reconcile(self, input: PoolInput) -> None:
        # Pending pilots count as live, so a full cluster doesn't make us pile on Jobs.
        live: int = await orchestrator_activity(
            "count_live_pilots", input.spec.request_id, result_type=int
        )
        desired = min(self._outstanding, input.max_workers)
        if live < desired:
            # A new generation per launch keeps Job names unique, and lets a retried
            # launch_pilots hit AlreadyExists instead of creating extra pilots.
            self._generation += 1
            await orchestrator_activity(
                "launch_pilots",
                LaunchPilotsInput(input.spec, desired - live, self._generation),
            )
