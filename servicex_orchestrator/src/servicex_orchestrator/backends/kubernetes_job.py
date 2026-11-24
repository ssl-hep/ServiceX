"""Transformer pilots as single-pod Kubernetes Jobs (plan §4.4).

The pod is the one `servicex_app.transformer_manager.TransformerManager` builds for a
Deployment today (science container, sidecar, Vector, the generated-code ConfigMap,
x509, CVMFS and output volumes), ported here because the orchestrator doesn't import
the app. The differences:

- It's a Job that runs once: `backoffLimit: 0` and `restartPolicy: Never`, since
  Temporal, not Kubernetes, retries the file a dead pilot was holding.
- The sidecar is a Temporal pilot that polls `transform-<request_id>`, configured by
  environment (the "pilot contract" below), not a Celery worker.
- Vector is a native sidecar (an init container with `restartPolicy: Always`), so
  Kubernetes stops it once the pilot and science containers exit and the Job can
  complete. Needs Kubernetes 1.29 or later.

Pilot contract: the sidecar container gets TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE,
TEMPORAL_TASK_QUEUE, REQUEST_ID, RESULT_DESTINATION, RESULT_FORMAT, SHARED_DIR,
WORKER_IDLE_TIMEOUT_SECONDS and, for the volume destination, OUTPUT_DIR.
"""

import asyncio
import logging
import os
from typing import Any, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

from servicex_orchestrator.backends.base import pilot_job_name
from servicex_orchestrator.backends.pod_config import TransformerPodConfig
from servicex_orchestrator.config import transform_task_queue
from servicex_orchestrator.models import PoolSpec

logger = logging.getLogger(__name__)

REQUEST_ID_LABEL = "servicex/request-id"
GENERATION_LABEL = "servicex/generation"
POSIX_VOLUME_MOUNT = "/posix_volume"
OBJECT_STORE_DEST = "object-store"
VOLUME_DEST = "volume"
# Job conditions after which a Job's pod is gone or going. SuccessCriteriaMet and
# FailureTarget come before Complete/Failed on Kubernetes 1.31+.
TERMINAL_JOB_CONDITIONS = frozenset(
    {"Complete", "Failed", "SuccessCriteriaMet", "FailureTarget"}
)


def generated_code_config_map(request_id: str) -> str:
    """The name the app's code generator gives the request's ConfigMap."""
    return f"{request_id}-generated-source"


def request_selector(request_id: str) -> str:
    return f"{REQUEST_ID_LABEL}={request_id}"


def load_kube_config() -> None:
    """In-cluster credentials, or ~/.kube/config when running outside a cluster."""
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()


# ----- pod template ---------------------------------------------------------------


def _env(name: str, value: Any) -> client.V1EnvVar:
    return client.V1EnvVar(name=name, value=str(value))


def _field_env(name: str, field_path: str) -> client.V1EnvVar:
    return client.V1EnvVar(
        name=name,
        value_from=client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(field_path=field_path)
        ),
    )


def _volumes(
    spec: PoolSpec, cfg: TransformerPodConfig
) -> tuple[list[Any], list[client.V1VolumeMount]]:
    """Volumes of the pod, and the mounts shared by the sidecar and science containers.

    Site-provided volume sources (CVMFS) are plain dicts in Kubernetes' own shape; the
    API client sends them as they are.
    """
    volumes: list[Any] = [
        client.V1Volume(
            name="sidecar-volume", empty_dir=client.V1EmptyDirVolumeSource()
        )
    ]
    mounts = [client.V1VolumeMount(name="sidecar-volume", mount_path=cfg.output_dir)]

    if cfg.mount_local:
        for name, host_path, mount_path in (
            ("host-volume", "/mnt/servicex/transformer_sidecar/src", "/servicex"),
            (
                "host-scripts-volume",
                "/mnt/servicex/transformer_sidecar/scripts",
                "/servicex/scripts",
            ),
        ):
            volumes.append(
                client.V1Volume(
                    name=name,
                    host_path=client.V1HostPathVolumeSource(
                        path=host_path, type="DirectoryOrCreate"
                    ),
                )
            )
            mounts.append(client.V1VolumeMount(name=name, mount_path=mount_path))

    if cfg.x509_secret:
        volumes.append(
            client.V1Volume(
                name="x509-secret",
                secret=client.V1SecretVolumeSource(secret_name=cfg.x509_secret),
            )
        )
        mounts.append(
            client.V1VolumeMount(name="x509-secret", mount_path="/etc/grid-security-ro")
        )

    # The transformer code the app's code generator wrote for this request
    if spec.generated_code_cm:
        volumes.append(
            client.V1Volume(
                name="generated-code",
                config_map=client.V1ConfigMapVolumeSource(name=spec.generated_code_cm),
            )
        )
        mounts.append(
            client.V1VolumeMount(name="generated-code", mount_path="/generated")
        )

    if cfg.host_mount:
        volumes.append(
            client.V1Volume(
                name="rootfiles",
                host_path=client.V1HostPathVolumeSource(path=cfg.host_mount),
            )
        )
        mounts.append(client.V1VolumeMount(name="rootfiles", mount_path="/data"))

    if cfg.cvmfs_volume:
        volumes.append({**cfg.cvmfs_volume, "name": "cvmfs"})
        mounts.append(
            client.V1VolumeMount(
                name="cvmfs",
                mount_path="/cvmfs",
                read_only=True,
                mount_propagation=(
                    "HostToContainer" if "hostPath" in cfg.cvmfs_volume else None
                ),
            )
        )

    if spec.result_destination == VOLUME_DEST:
        if cfg.persistence_claim:
            volumes.append(
                client.V1Volume(
                    name="posix-volume",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=cfg.persistence_claim
                    ),
                )
            )
        else:
            volumes.append(
                client.V1Volume(
                    name="posix-volume", empty_dir=client.V1EmptyDirVolumeSource()
                )
            )
        mounts.append(
            client.V1VolumeMount(name="posix-volume", mount_path=POSIX_VOLUME_MOUNT)
        )

    if cfg.vector:
        volumes += [
            client.V1Volume(
                name="vector-config",
                config_map=client.V1ConfigMapVolumeSource(name=cfg.vector.config_map),
            ),
            client.V1Volume(
                name="vector-data", empty_dir=client.V1EmptyDirVolumeSource()
            ),
        ]
    return volumes, mounts


def _shared_env(spec: PoolSpec, cfg: TransformerPodConfig) -> list[client.V1EnvVar]:
    """Environment of both the sidecar and the science container."""
    env = [
        _env("BASH_ENV", "/servicex/.bashrc"),
        _env("LOG_LEVEL", cfg.log_level),
        _env("INSTANCE_NAME", cfg.instance_name),
        _field_env("POD_NAME", "metadata.name"),
        _field_env("HOST_NAME", "spec.nodeName"),
    ]
    if cfg.vector:
        # The sidecar logs to the pod's own Vector
        env += [_env("VECTOR_HOST", "127.0.0.1"), _env("VECTOR_PORT", cfg.vector.port)]
    if cfg.cache_prefix:
        env.append(_env("CACHE_PREFIX", cfg.cache_prefix))
    if spec.result_destination == OBJECT_STORE_DEST and cfg.object_store:
        env += [
            _env("MINIO_URL", cfg.object_store.url),
            _env("MINIO_ACCESS_KEY", cfg.object_store.access_key),
            _env("MINIO_SECRET_KEY", cfg.object_store.secret_key),
        ]
        if cfg.object_store.encrypt is not None:
            env.append(_env("MINIO_ENCRYPT", cfg.object_store.encrypt))
    return env


def _pilot_env(spec: PoolSpec, cfg: TransformerPodConfig) -> list[client.V1EnvVar]:
    """The sidecar's pilot contract."""
    env = [
        _env("TEMPORAL_ADDRESS", cfg.temporal_address),
        _env("TEMPORAL_NAMESPACE", cfg.temporal_namespace),
        _env("TEMPORAL_TASK_QUEUE", transform_task_queue(spec.request_id)),
        _env("REQUEST_ID", spec.request_id),
        _env("RESULT_DESTINATION", spec.result_destination),
        _env("RESULT_FORMAT", spec.result_format),
        _env("SHARED_DIR", cfg.output_dir),
        _env("WORKER_IDLE_TIMEOUT_SECONDS", cfg.idle_timeout_seconds),
    ]
    if spec.result_destination == VOLUME_DEST:
        env.append(
            _env("OUTPUT_DIR", os.path.join(POSIX_VOLUME_MOUNT, cfg.persistence_subdir))
        )
    return env


def _science_command(spec: PoolSpec, cfg: TransformerPodConfig) -> str:
    command = " "
    if cfg.x509_secret:
        # Wait for the sidecar to publish the proxy exporter, then keep it running
        command += (
            "until [ -f /servicex/output/scripts/proxy-exporter.sh ];"
            "do sleep 5;done &&"
            " /servicex/output/scripts/proxy-exporter.sh & sleep 5 && "
        )
    watch_path = os.path.join(cfg.output_dir, spec.request_id)
    command += (
        f"cp /generated/transformer_capabilities.json {cfg.output_dir} && "
        "PYTHONPATH=/generated:$PYTHONPATH "
        f"bash {cfg.output_dir}/scripts/watch.sh "
        f"{spec.transformer_language} {spec.transformer_command} {watch_path}"
    )
    return command


def _vector_container(
    spec: PoolSpec, cfg: TransformerPodConfig
) -> Optional[client.V1Container]:
    """Vector as a native sidecar: it tails the science container's logs off the
    shared volume and receives the pilot's over localhost.

    It has its own mount list: the science and sidecar containers share theirs, and
    Vector's config doesn't belong in them. No --watch-config: the watcher takes an
    inotify instance, and a node packed with pilots runs out of them.
    """
    vector = cfg.vector
    if vector is None:
        return None
    return client.V1Container(
        name="vector",
        image=vector.image,
        image_pull_policy=vector.pull_policy,
        restart_policy="Always",
        args=["--config", "/etc/vector/vector.yaml"],
        env=[
            _env("VECTOR_LOG", vector.log_level),
            # One thread per node core otherwise, and memory grows with threads
            _env("VECTOR_THREADS", vector.threads),
            # Interpolated by the vector config; Vector won't start without them
            _env("REQUEST_ID", spec.request_id),
            _field_env("POD_NAME", "metadata.name"),
            _field_env("HOST_NAME", "spec.nodeName"),
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="sidecar-volume", mount_path=cfg.output_dir, read_only=True
            ),
            client.V1VolumeMount(
                name="vector-config", mount_path="/etc/vector", read_only=True
            ),
            client.V1VolumeMount(name="vector-data", mount_path="/vector-data-dir"),
        ],
        resources=client.V1ResourceRequirements(
            limits=vector.resources.get("limits"),
            requests=vector.resources.get("requests"),
        ),
    )


def build_pilot_job(
    spec: PoolSpec, generation: int, index: int, cfg: TransformerPodConfig
) -> client.V1Job:
    """The Job for one pilot of the request. Pure: no API calls."""
    volumes, mounts = _volumes(spec, cfg)
    shared_env = _shared_env(spec, cfg)
    resources = client.V1ResourceRequirements(
        limits={"cpu": cfg.cpu_limit, "memory": cfg.memory_limit},
        requests={"cpu": cfg.cpu_request, "memory": cfg.memory_request},
    )

    sidecar = client.V1Container(
        name="sidecar",
        image=cfg.sidecar_image,
        image_pull_policy=cfg.sidecar_pull_policy,
        command=list(cfg.sidecar_command),
        env=shared_env + _pilot_env(spec, cfg),
        volume_mounts=mounts,
        resources=resources,
    )
    science = client.V1Container(
        name="transformer",
        image=spec.image,
        image_pull_policy=cfg.science_pull_policy,
        command=["bash", "--login", "-c"],
        args=[_science_command(spec, cfg)],
        env=shared_env,
        volume_mounts=mounts,
        resources=resources,
    )
    vector = _vector_container(spec, cfg)

    labels = {
        "app": f"transformer-{spec.request_id}",
        REQUEST_ID_LABEL: spec.request_id,
        GENERATION_LABEL: str(generation),
    }
    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        termination_grace_period_seconds=cfg.termination_grace_period_seconds,
        priority_class_name=cfg.priority_class,
        node_selector=cfg.node_selector or None,
        tolerations=cfg.tolerations or None,
        affinity=cfg.affinity or None,
        init_containers=[vector] if vector else None,
        containers=[sidecar, science],  # started in this order
        volumes=volumes,
    )
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=pilot_job_name(spec.request_id, generation, index),
            namespace=cfg.namespace,
            labels=labels,
        ),
        spec=client.V1JobSpec(
            # Temporal retries the file; a restarted pod would only race it.
            backoff_limit=0,
            ttl_seconds_after_finished=cfg.ttl_seconds_after_finished,
            active_deadline_seconds=cfg.active_deadline_seconds,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels=labels, annotations=cfg.pod_annotations or None
                ),
                spec=pod_spec,
            ),
        ),
    )


def is_live(job: client.V1Job) -> bool:
    """Not finished. A Job whose pod is still Pending is live."""
    conditions = (job.status and job.status.conditions) or []
    return not any(
        c.type in TERMINAL_JOB_CONDITIONS and c.status == "True" for c in conditions
    )


# ----- backend ----------------------------------------------------------------------


class KubernetesJobBackend:
    """WorkerBackend on Kubernetes Jobs, in the transformer namespace.

    The kubernetes client is synchronous, so each call runs in a thread. API errors
    other than the expected 404/409 propagate, and Temporal retries the activity.
    """

    def __init__(
        self,
        cfg: TransformerPodConfig,
        batch_api: Optional[client.BatchV1Api] = None,
        core_api: Optional[client.CoreV1Api] = None,
    ):
        self.cfg = cfg
        self.batch_api = batch_api or client.BatchV1Api()
        self.core_api = core_api or client.CoreV1Api()

    async def count_live_pilots(self, request_id: str) -> int:
        jobs = await asyncio.to_thread(
            self.batch_api.list_namespaced_job,
            self.cfg.namespace,
            label_selector=request_selector(request_id),
        )
        return sum(1 for job in jobs.items if is_live(job))

    async def launch_pilots(self, spec: PoolSpec, count: int, generation: int) -> None:
        for index in range(count):
            job = build_pilot_job(spec, generation, index, self.cfg)
            try:
                await asyncio.to_thread(
                    self.batch_api.create_namespaced_job, self.cfg.namespace, job
                )
            except ApiException as err:
                if err.status != 409:
                    raise
                # A retried launch: this pilot was created by an earlier attempt.
                logger.info(
                    "Pilot %s already exists",
                    job.metadata.name,
                    extra={"request_id": spec.request_id},
                )

    async def delete_pool(self, request_id: str) -> None:
        # Background propagation: pods get SIGTERM and their grace period.
        await asyncio.to_thread(
            self.batch_api.delete_collection_namespaced_job,
            self.cfg.namespace,
            label_selector=request_selector(request_id),
            propagation_policy="Background",
        )

    async def cleanup_request(self, request_id: str) -> None:
        await self.delete_pool(request_id)
        try:
            await asyncio.to_thread(
                self.core_api.delete_namespaced_config_map,
                generated_code_config_map(request_id),
                self.cfg.namespace,
            )
        except ApiException as err:
            if err.status != 404:
                raise
