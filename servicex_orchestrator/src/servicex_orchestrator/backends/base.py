"""The interface between the pool manager and whatever runs transformer pilots.

PoolManagerWorkflow only ever asks three things of a backend: how many of a
request's pilots are still alive, to start some more, and to remove them all. The
request workflow also asks it to clean up what the request left behind. Kubernetes
Jobs implement it now (`kubernetes_job.py`); HTCondor will later, with no workflow
changes (plan §4.4).

Every method must be idempotent: the activities that call them are retried.
"""

from typing import Protocol

from servicex_orchestrator.models import PoolSpec


def pilot_job_name(request_id: str, generation: int, index: int) -> str:
    """Deterministic per (generation, index), so a retried launch can't add pilots."""
    return f"transformer-{request_id}-{generation}-{index}"


class WorkerBackend(Protocol):
    async def count_live_pilots(self, request_id: str) -> int:
        """Pilots of the request that haven't finished, pending ones included."""
        ...

    async def launch_pilots(self, spec: PoolSpec, count: int, generation: int) -> None:
        """Start `count` pilots, named by `generation`. Re-launching a name that
        already exists counts as success."""
        ...

    async def delete_pool(self, request_id: str) -> None:
        """Remove every pilot of the request. Nothing to remove is success."""
        ...

    async def cleanup_request(self, request_id: str) -> None:
        """Remove what the request left on the cluster: leftover pilots and the
        generated-code ConfigMap. Nothing to remove is success."""
        ...
