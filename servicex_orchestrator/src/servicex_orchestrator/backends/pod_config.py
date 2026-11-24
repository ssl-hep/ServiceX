"""Cluster settings for transformer pilot pods, read from a JSON file.

Helm renders the file (`<release>-orchestrator-transformer` ConfigMap) from the same
values the app's `TRANSFORMER_*` settings come from, and the orchestrator reads it at
start-up (`TRANSFORMER_CONFIG_FILE`). Keys are snake_case. Kubernetes fragments a site
writes in its values (`cvmfs_volume`, `tolerations`, `affinity`, `vector.resources`)
are kept verbatim in Kubernetes' own camelCase shape and go into the pod spec as is.

The object-store credentials are not in the file: they come from the orchestrator's
environment (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`), set from the release's Secret.
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional

DEFAULT_SIDECAR_COMMAND = (
    "bash",
    "-c",
    "PYTHONPATH=/servicex/transformer_sidecar:$PYTHONPATH "
    "python /servicex/transformer_sidecar/pilot.py",
)


@dataclass(frozen=True)
class VectorConfig:
    """The per-pod Vector that forwards the pilot's logs to the release's aggregator."""

    image: str
    config_map: str
    pull_policy: str = "IfNotPresent"
    port: int = 9000
    log_level: str = "info"
    threads: int = 2
    resources: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VectorConfig":
        return cls(
            image=data["image"],
            config_map=data["config_map"],
            pull_policy=data.get("pull_policy", "IfNotPresent"),
            port=int(data.get("port", 9000)),
            log_level=data.get("log_level", "info"),
            threads=int(data.get("threads", 2)),
            resources=dict(data.get("resources") or {}),
        )


@dataclass(frozen=True)
class ObjectStoreConfig:
    url: str
    encrypt: Optional[bool] = None
    access_key: str = field(default="", repr=False)
    secret_key: str = field(default="", repr=False)


@dataclass(frozen=True)
class TransformerPodConfig:
    namespace: str
    sidecar_image: str
    # Where the pilot reaches Temporal. Pilots poll transform-<request_id>.
    temporal_address: str
    temporal_namespace: str
    sidecar_pull_policy: str = "Always"
    sidecar_command: tuple[str, ...] = DEFAULT_SIDECAR_COMMAND
    science_pull_policy: str = "Always"
    cpu_limit: str = "1"
    cpu_request: str = "1"
    memory_limit: str = "4Gi"
    memory_request: str = "1Gi"
    # Shared by the sidecar and science containers; the science container's logs and
    # the transformed files are written under it.
    output_dir: str = "/servicex/output"
    instance_name: str = "Unknown"
    log_level: str = "INFO"
    x509_secret: Optional[str] = None
    cvmfs_volume: Optional[dict] = None
    # A host directory mounted at /data (the chart's `hostMount`)
    host_mount: Optional[str] = None
    # Dev only: mount the sidecar's source from the host
    mount_local: bool = False
    persistence_claim: Optional[str] = None
    persistence_subdir: str = ""
    cache_prefix: Optional[str] = None
    node_selector: dict = field(default_factory=dict)
    tolerations: list = field(default_factory=list)
    affinity: dict = field(default_factory=dict)
    pod_annotations: dict = field(default_factory=dict)
    priority_class: Optional[str] = None
    vector: Optional[VectorConfig] = None
    object_store: Optional[ObjectStoreConfig] = None
    # A pilot exits after this long without work (passed to the pilot)
    idle_timeout_seconds: int = 120
    # Backstop on a pilot's whole life; Temporal's own timeouts come first.
    active_deadline_seconds: int = 24 * 60 * 60
    ttl_seconds_after_finished: int = 300
    # Time the pilot gets on SIGTERM to finish and upload the file in hand
    termination_grace_period_seconds: int = 5 * 60

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], env: Mapping[str, str] = os.environ
    ) -> "TransformerPodConfig":
        sidecar = data.get("sidecar") or {}
        science = data.get("science") or {}
        resources = data.get("resources") or {}
        limits = resources.get("limits") or {}
        requests = resources.get("requests") or {}
        temporal = data.get("temporal") or {}
        persistence = data.get("persistence") or {}
        pilot = data.get("pilot") or {}
        vector = data.get("vector")
        object_store = data.get("object_store")
        return cls(
            namespace=data["namespace"],
            sidecar_image=sidecar["image"],
            sidecar_pull_policy=sidecar.get("pull_policy", "Always"),
            sidecar_command=tuple(sidecar.get("command") or DEFAULT_SIDECAR_COMMAND),
            science_pull_policy=science.get("pull_policy", "Always"),
            temporal_address=temporal["address"],
            temporal_namespace=temporal["namespace"],
            cpu_limit=str(limits.get("cpu", "1")),
            cpu_request=str(requests.get("cpu", "1")),
            memory_limit=str(limits.get("memory", "4Gi")),
            memory_request=str(requests.get("memory", "1Gi")),
            output_dir=data.get("output_dir", "/servicex/output"),
            instance_name=data.get("instance_name", "Unknown"),
            log_level=str(data.get("log_level", "INFO")).upper(),
            x509_secret=data.get("x509_secret") or None,
            cvmfs_volume=data.get("cvmfs_volume") or None,
            host_mount=data.get("host_mount") or None,
            mount_local=bool(data.get("mount_local", False)),
            persistence_claim=persistence.get("existing_claim") or None,
            persistence_subdir=persistence.get("subdir") or "",
            cache_prefix=data.get("cache_prefix") or None,
            node_selector=dict(data.get("node_selector") or {}),
            tolerations=list(data.get("tolerations") or []),
            affinity=dict(data.get("affinity") or {}),
            pod_annotations=dict(data.get("pod_annotations") or {}),
            priority_class=data.get("priority_class") or None,
            vector=VectorConfig.from_dict(vector) if vector else None,
            object_store=(
                ObjectStoreConfig(
                    url=object_store["url"],
                    encrypt=object_store.get("encrypt"),
                    access_key=env.get("MINIO_ACCESS_KEY", ""),
                    secret_key=env.get("MINIO_SECRET_KEY", ""),
                )
                if object_store
                else None
            ),
            idle_timeout_seconds=int(pilot.get("idle_timeout_seconds", 120)),
            active_deadline_seconds=int(
                pilot.get("active_deadline_seconds", 24 * 60 * 60)
            ),
            ttl_seconds_after_finished=int(
                pilot.get("ttl_seconds_after_finished", 300)
            ),
            termination_grace_period_seconds=int(
                pilot.get("termination_grace_period_seconds", 5 * 60)
            ),
        )

    @classmethod
    def from_file(
        cls, path: str, env: Mapping[str, str] = os.environ
    ) -> "TransformerPodConfig":
        with open(path) as f:
            return cls.from_dict(json.load(f), env)
