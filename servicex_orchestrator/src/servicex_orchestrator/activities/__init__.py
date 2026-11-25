from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from servicex_orchestrator.activities.datasets import DatasetActivities
from servicex_orchestrator.activities.files import FileActivities
from servicex_orchestrator.activities.health import ping
from servicex_orchestrator.activities.pool import PoolActivities
from servicex_orchestrator.activities.request_status import RequestActivities
from servicex_orchestrator.activities.stubs import StubActivities, StubPoolBackend
from servicex_orchestrator.backends.base import WorkerBackend
from servicex_orchestrator.config import (
    KUBERNETES_BACKEND,
    STUB_BACKEND,
    WORKER_BACKENDS,
    Settings,
)


def build_stubs(settings: Settings) -> StubActivities:
    return StubActivities(
        stub_files=settings.stub_dataset_files,
        stub_delay=settings.stub_activity_delay_seconds,
    )


def build_backend(settings: Settings) -> WorkerBackend:
    """The WorkerBackend WORKER_BACKEND names. Raises ValueError on a bad setting,
    so a misconfigured orchestrator fails at start-up, not on its first request."""
    if settings.worker_backend == STUB_BACKEND:
        return StubPoolBackend(build_stubs(settings))
    if settings.worker_backend == KUBERNETES_BACKEND:
        if not settings.transformer_config_file:
            raise ValueError(
                "WORKER_BACKEND=kubernetes needs TRANSFORMER_CONFIG_FILE, the "
                "transformer pod settings"
            )
        # Imported here so the stub setup never needs a kube config
        from servicex_orchestrator.backends.kubernetes_job import (
            KubernetesJobBackend,
            load_kube_config,
        )
        from servicex_orchestrator.backends.pod_config import TransformerPodConfig

        cfg = TransformerPodConfig.from_file(settings.transformer_config_file)
        load_kube_config()
        return KubernetesJobBackend(cfg)
    raise ValueError(
        f"Unknown WORKER_BACKEND {settings.worker_backend!r}; "
        f"expected one of {', '.join(WORKER_BACKENDS)}"
    )


def build_db_activities(engine: AsyncEngine) -> list:
    """The activities that read and write the ServiceX Postgres."""
    return [
        *DatasetActivities(engine).all(),
        *RequestActivities(engine).all(),
        *FileActivities(engine).all(),
    ]


def build_activities(
    settings: Settings,
    engine: Optional[AsyncEngine] = None,
    *,
    db_activities: Optional[list] = None,
    backend: Optional[WorkerBackend] = None,
) -> list:
    """Every activity the orchestrator's own queue serves.

    The DB activities are built on `engine` (the ServiceX Postgres pool) unless
    `db_activities` is given, as tests do with in-memory fakes. The pool activities
    run on `backend`, or the one `settings.worker_backend` names.
    """
    if db_activities is None:
        if engine is None:
            raise ValueError("build_activities needs a database engine")
        db_activities = build_db_activities(engine)
    if backend is None:
        backend = build_backend(settings)
    return [
        ping,
        *db_activities,
        *build_stubs(settings).all(),
        *PoolActivities(backend).all(),
    ]


__all__ = [
    "DatasetActivities",
    "FileActivities",
    "PoolActivities",
    "RequestActivities",
    "StubActivities",
    "StubPoolBackend",
    "build_activities",
    "build_backend",
    "build_db_activities",
    "build_stubs",
    "ping",
]
