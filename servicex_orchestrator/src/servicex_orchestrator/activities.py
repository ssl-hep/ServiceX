import socket

from temporalio import activity


@activity.defn
async def ping(message: str) -> str:
    """Echo the message back with the name of the worker pod that ran it.

    Used by PingWorkflow to check that the orchestrator is polling its task queue.
    """
    return f"pong from {socket.gethostname()}: {message}"


ACTIVITIES = [ping]
