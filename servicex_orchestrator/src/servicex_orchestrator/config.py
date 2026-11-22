import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_TASK_QUEUE = "servicex-orchestrator"


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the orchestrator worker, read from the environment."""

    temporal_address: str
    temporal_namespace: str
    task_queue: str
    log_level: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            temporal_address=env.get("TEMPORAL_ADDRESS", "localhost:7233"),
            temporal_namespace=env.get("TEMPORAL_NAMESPACE", "default"),
            task_queue=env.get("TEMPORAL_TASK_QUEUE", DEFAULT_TASK_QUEUE),
            log_level=env.get("LOG_LEVEL", "INFO").upper(),
        )
