"""Helpers shared by the workflows."""

import asyncio
from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import (
    ActivityError,
    ApplicationError,
    CancelledError,
    FailureError,
)

# DB / Kubernetes / object-store activities on the orchestrator (plan §5.3): short
# timeout, unlimited retries with capped backoff, so a Postgres or API-server blip
# stalls the request instead of failing it.
ORCHESTRATOR_TIMEOUT = timedelta(seconds=30)
ORCHESTRATOR_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)


async def orchestrator_activity(
    name: str, *args: Any, result_type: Optional[type] = None
) -> Any:
    """Run one of the orchestrator's own activities by name."""
    return await workflow.execute_activity(
        name,
        args=list(args),
        result_type=result_type,
        start_to_close_timeout=ORCHESTRATOR_TIMEOUT,
        retry_policy=ORCHESTRATOR_RETRY,
    )


async def signal_workflow(workflow_id: str, signal: str, *args: Any) -> bool:
    """Signal another workflow. Returns False if it is gone (closed or never existed).

    Raises asyncio.CancelledError if our workflow was canceled meanwhile. The SDK
    can't always do that itself: a cancel that arrives while the signal is pending
    is applied to the signal, and if the signal had already reached the server the
    await returns normally and the cancellation is lost. Temporal treats
    cancellation as a state, so check it.
    """
    try:
        await workflow.get_external_workflow_handle(workflow_id).signal(
            signal, args=list(args)
        )
        delivered = True
    except CancelledError as err:
        # The pending signal was canceled along with us. That is Temporal's
        # CancelledError, a FailureError: don't mistake it for "target gone".
        raise asyncio.CancelledError() from err
    except FailureError as err:
        workflow.logger.info("Could not signal %s to %s: %s", signal, workflow_id, err)
        delivered = False
    if workflow.cancellation_reason() is not None:
        raise asyncio.CancelledError()
    return delivered


def error_type(err: ActivityError) -> tuple[str, str]:
    """The (type, message) of the error that made an activity fail for good."""
    cause = err.cause
    if isinstance(cause, ApplicationError):
        return cause.type or "ApplicationError", cause.message
    if cause is not None:
        return type(cause).__name__, str(cause)
    return type(err).__name__, str(err)
