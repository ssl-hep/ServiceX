import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_TASK_QUEUE = "servicex-orchestrator"

# What runs transformer pilots (WORKER_BACKEND)
STUB_BACKEND = "stub"
KUBERNETES_BACKEND = "kubernetes"
WORKER_BACKENDS = (STUB_BACKEND, KUBERNETES_BACKEND)


def did_finder_task_queue(scheme: str) -> str:
    """The queue the DID finder for `scheme` polls for `lookup_dataset`."""
    return f"did-finder-{scheme}"


def transform_task_queue(request_id: str) -> str:
    """The queue a request's transformer pilots poll for `transform_file`."""
    return f"transform-{request_id}"


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the orchestrator worker, read from the environment."""

    temporal_address: str
    temporal_namespace: str
    task_queue: str
    log_level: str
    # Size of the fake dataset every stub DID lookup "finds"
    stub_dataset_files: int = 25
    # How long stub lookup chunks and stub transforms pretend to take
    stub_activity_delay_seconds: float = 0.5
    # The release's Vector aggregator. Logs go only to stdout when unset.
    vector_host: Optional[str] = None
    vector_port: Optional[int] = None
    instance_name: str = "Unknown"
    # DID schemes whose `did-finder-<scheme>` queue this worker serves with the stub
    # lookup, for setups without a real DID finder. A tuple keeps Settings hashable.
    stub_did_finder_schemes: tuple[str, ...] = ()
    # The ServiceX Postgres, as the orchestrator's own restricted role. Kept out of
    # repr() because it holds the password. Optional while every DB activity is
    # still a stub.
    database_url: Optional[str] = field(default=None, repr=False)
    # Connection pool per replica: at most pool size + overflow connections each.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    # `stub` logs pilot launches; `kubernetes` creates a Job per pilot, with the pod
    # settings read from `transformer_config_file`.
    worker_backend: str = STUB_BACKEND
    transformer_config_file: Optional[str] = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            temporal_address=env.get("TEMPORAL_ADDRESS", "localhost:7233"),
            temporal_namespace=env.get("TEMPORAL_NAMESPACE", "default"),
            task_queue=env.get("TEMPORAL_TASK_QUEUE", DEFAULT_TASK_QUEUE),
            log_level=env.get("LOG_LEVEL", "INFO").upper(),
            stub_dataset_files=int(env.get("STUB_DATASET_FILES", "25")),
            stub_activity_delay_seconds=float(
                env.get("STUB_ACTIVITY_DELAY_SECONDS", "0.5")
            ),
            vector_host=env.get("VECTOR_HOST") or None,
            vector_port=int(env["VECTOR_PORT"]) if env.get("VECTOR_PORT") else None,
            instance_name=env.get("INSTANCE_NAME", "Unknown"),
            stub_did_finder_schemes=_split_list(env.get("STUB_DID_FINDER_SCHEMES", "")),
            database_url=env.get("DATABASE_URL") or None,
            db_pool_size=int(env.get("DB_POOL_SIZE", "5")),
            db_max_overflow=int(env.get("DB_MAX_OVERFLOW", "5")),
            worker_backend=env.get("WORKER_BACKEND", STUB_BACKEND).strip().lower(),
            transformer_config_file=env.get("TRANSFORMER_CONFIG_FILE") or None,
        )
