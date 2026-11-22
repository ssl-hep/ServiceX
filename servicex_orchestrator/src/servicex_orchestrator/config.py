import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

DEFAULT_TASK_QUEUE = "servicex-orchestrator"


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
        )
