import dataclasses
import json
from types import SimpleNamespace

import pytest
from kubernetes import client
from kubernetes.client.rest import ApiException

from servicex_orchestrator.activities import StubPoolBackend, build_backend
from servicex_orchestrator.backends.kubernetes_job import (
    KubernetesJobBackend,
    build_pilot_job,
    is_live,
)
from servicex_orchestrator.backends.pod_config import (
    DEFAULT_SIDECAR_COMMAND,
    TransformerPodConfig,
)
from servicex_orchestrator.config import Settings
from servicex_orchestrator.models import PoolSpec

REQUEST_ID = "0b2ad0c8-4e0e-4b5e-9d0c-6f4d8f3a1e2b"

FULL_CONFIG = {
    "namespace": "servicex",
    "instance_name": "servicex-test",
    "log_level": "debug",
    "temporal": {"address": "servicex-temporal-frontend:7233", "namespace": "servicex"},
    "sidecar": {"image": "sslhep/servicex_sidecar:develop", "pull_policy": "Always"},
    "science": {"pull_policy": "IfNotPresent"},
    "resources": {
        "limits": {"cpu": 1, "memory": "4Gi"},
        "requests": {"cpu": "500m", "memory": "2Gi"},
    },
    "output_dir": "/servicex/output",
    "x509_secret": "x509-proxy",
    "cvmfs_volume": {"hostPath": {"path": "/cvmfs"}},
    "host_mount": "/data/rootfiles",
    "persistence": {"existing_claim": "", "subdir": "results"},
    "cache_prefix": "xcache.example.org:1094",
    "node_selector": {"servicex": "transformers"},
    "tolerations": [{"key": "dedicated", "operator": "Exists", "effect": "NoSchedule"}],
    "affinity": {
        "nodeAffinity": {"preferredDuringSchedulingIgnoredDuringExecution": []}
    },
    "pod_annotations": {"example.org/team": "servicex"},
    "priority_class": "transformers",
    "vector": {
        "image": "timberio/vector:0.50.0-debian",
        "config_map": "servicex-transformer-vector-config",
        "pull_policy": "IfNotPresent",
        "port": 9000,
        "log_level": "info",
        "threads": 2,
        "resources": {"requests": {"cpu": "50m", "memory": "64Mi"}},
    },
    "object_store": {"url": "servicex-minio:9000", "encrypt": False},
    "pilot": {"idle_timeout_seconds": 90, "active_deadline_seconds": 3600},
}
ENV = {"MINIO_ACCESS_KEY": "miniouser", "MINIO_SECRET_KEY": "leftfoot1"}


def _spec(**changes) -> PoolSpec:
    spec = PoolSpec(
        request_id=REQUEST_ID,
        image="sslhep/servicex_func_adl_uproot_transformer:develop",
        generated_code_cm=f"{REQUEST_ID}-generated-source",
        transformer_language="python",
        transformer_command="/generated/transform_single_file.py",
        result_destination="object-store",
        result_format="parquet",
    )
    return dataclasses.replace(spec, **changes)


def _config(**changes) -> TransformerPodConfig:
    return dataclasses.replace(
        TransformerPodConfig.from_dict(FULL_CONFIG, ENV), **changes
    )


def _render(job: client.V1Job) -> dict:
    """The Job as the API server receives it."""
    return client.ApiClient().sanitize_for_serialization(job)


def _containers(pod: dict) -> dict:
    return {c["name"]: c for c in pod["containers"] + pod.get("initContainers", [])}


def _env(container: dict) -> dict:
    return {e["name"]: e.get("value", e.get("valueFrom")) for e in container["env"]}


def _mounts(container: dict) -> dict:
    return {m["name"]: m for m in container["volumeMounts"]}


# ----- config ---------------------------------------------------------------------


def test_config_from_file(tmp_path):
    path = tmp_path / "transformer.json"
    path.write_text(json.dumps(FULL_CONFIG))
    cfg = TransformerPodConfig.from_file(str(path), ENV)
    assert cfg == TransformerPodConfig.from_dict(FULL_CONFIG, ENV)
    assert cfg.cpu_limit == "1"
    assert cfg.log_level == "DEBUG"
    assert cfg.persistence_claim is None  # "" means no claim
    assert cfg.object_store.access_key == "miniouser"
    assert "leftfoot1" not in repr(cfg)
    assert cfg.vector.config_map == "servicex-transformer-vector-config"
    assert cfg.idle_timeout_seconds == 90
    assert cfg.ttl_seconds_after_finished == 300


def test_minimal_config_defaults():
    cfg = TransformerPodConfig.from_dict(
        {
            "namespace": "servicex",
            "temporal": {"address": "t:7233", "namespace": "servicex"},
            "sidecar": {"image": "sidecar:1"},
        },
        {},
    )
    assert cfg.sidecar_command == DEFAULT_SIDECAR_COMMAND
    assert cfg.vector is None
    assert cfg.object_store is None
    assert cfg.x509_secret is None
    assert cfg.cvmfs_volume is None


# ----- the Job --------------------------------------------------------------------


def test_job_runs_once_and_is_labelled():
    job = _render(build_pilot_job(_spec(), 7, 2, _config()))
    assert job["kind"] == "Job"
    assert job["metadata"]["name"] == f"transformer-{REQUEST_ID}-7-2"
    assert len(job["metadata"]["name"]) <= 63
    assert job["metadata"]["namespace"] == "servicex"
    labels = {
        "app": f"transformer-{REQUEST_ID}",
        "servicex/request-id": REQUEST_ID,
        "servicex/generation": "7",
    }
    assert job["metadata"]["labels"] == labels
    assert job["spec"]["backoffLimit"] == 0
    assert job["spec"]["ttlSecondsAfterFinished"] == 300
    assert job["spec"]["activeDeadlineSeconds"] == 3600
    template = job["spec"]["template"]
    assert template["metadata"]["labels"] == labels
    assert template["metadata"]["annotations"] == {"example.org/team": "servicex"}
    pod = template["spec"]
    assert pod["restartPolicy"] == "Never"
    assert pod["terminationGracePeriodSeconds"] == 300
    assert pod["priorityClassName"] == "transformers"
    assert pod["nodeSelector"] == {"servicex": "transformers"}
    assert pod["tolerations"] == FULL_CONFIG["tolerations"]
    assert pod["affinity"] == FULL_CONFIG["affinity"]
    assert [c["name"] for c in pod["containers"]] == ["sidecar", "transformer"]


def test_generated_code_config_map_is_mounted():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["generated-code"] == {
        "name": "generated-code",
        "configMap": {"name": f"{REQUEST_ID}-generated-source"},
    }
    containers = _containers(pod)
    for name in ("sidecar", "transformer"):
        assert _mounts(containers[name])["generated-code"]["mountPath"] == "/generated"
    assert "generated-code" not in _mounts(containers["vector"])


def test_science_container_runs_the_generated_code():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    science = _containers(pod)["transformer"]
    assert science["image"] == _spec().image
    assert science["imagePullPolicy"] == "IfNotPresent"
    assert science["command"] == ["bash", "--login", "-c"]
    [command] = science["args"]
    assert "cp /generated/transformer_capabilities.json /servicex/output" in command
    assert "PYTHONPATH=/generated:$PYTHONPATH" in command
    assert command.endswith(
        "bash /servicex/output/scripts/watch.sh python "
        f"/generated/transform_single_file.py /servicex/output/{REQUEST_ID}"
    )
    # With an x509 secret it waits for the proxy exporter first
    assert command.index("proxy-exporter.sh") < command.index("watch.sh")
    assert science["resources"] == {
        "limits": {"cpu": "1", "memory": "4Gi"},
        "requests": {"cpu": "500m", "memory": "2Gi"},
    }


def test_sidecar_gets_the_pilot_contract():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    sidecar = _containers(pod)["sidecar"]
    assert sidecar["image"] == "sslhep/servicex_sidecar:develop"
    assert sidecar["command"] == list(DEFAULT_SIDECAR_COMMAND)
    env = _env(sidecar)
    assert env["TEMPORAL_ADDRESS"] == "servicex-temporal-frontend:7233"
    assert env["TEMPORAL_NAMESPACE"] == "servicex"
    assert env["TEMPORAL_TASK_QUEUE"] == f"transform-{REQUEST_ID}"
    assert env["REQUEST_ID"] == REQUEST_ID
    assert env["RESULT_DESTINATION"] == "object-store"
    assert env["RESULT_FORMAT"] == "parquet"
    assert env["SHARED_DIR"] == "/servicex/output"
    assert env["WORKER_IDLE_TIMEOUT_SECONDS"] == "90"
    assert "OUTPUT_DIR" not in env
    assert "TEMPORAL_ADDRESS" not in _env(_containers(pod)["transformer"])


def test_shared_env():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    containers = _containers(pod)
    for name in ("sidecar", "transformer"):
        env = _env(containers[name])
        assert env["LOG_LEVEL"] == "DEBUG"
        assert env["INSTANCE_NAME"] == "servicex-test"
        assert env["POD_NAME"] == {"fieldRef": {"fieldPath": "metadata.name"}}
        assert env["HOST_NAME"] == {"fieldRef": {"fieldPath": "spec.nodeName"}}
        assert env["CACHE_PREFIX"] == "xcache.example.org:1094"
        assert env["MINIO_URL"] == "servicex-minio:9000"
        assert env["MINIO_ACCESS_KEY"] == "miniouser"
        assert env["MINIO_SECRET_KEY"] == "leftfoot1"
        assert env["MINIO_ENCRYPT"] == "False"
        assert env["VECTOR_HOST"] == "127.0.0.1"
        assert env["VECTOR_PORT"] == "9000"


def test_site_volumes():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["x509-secret"]["secret"] == {"secretName": "x509-proxy"}
    assert volumes["cvmfs"] == {"name": "cvmfs", "hostPath": {"path": "/cvmfs"}}
    assert volumes["rootfiles"]["hostPath"] == {"path": "/data/rootfiles"}
    assert "posix-volume" not in volumes
    assert "host-volume" not in volumes
    mounts = _mounts(_containers(pod)["sidecar"])
    assert mounts["x509-secret"]["mountPath"] == "/etc/grid-security-ro"
    assert mounts["cvmfs"] == {
        "name": "cvmfs",
        "mountPath": "/cvmfs",
        "readOnly": True,
        "mountPropagation": "HostToContainer",
    }
    assert mounts["rootfiles"]["mountPath"] == "/data"
    assert mounts["sidecar-volume"]["mountPath"] == "/servicex/output"


def test_bare_config_has_only_the_essential_volumes():
    cfg = _config(
        x509_secret=None,
        cvmfs_volume=None,
        host_mount=None,
        vector=None,
        cache_prefix=None,
    )
    job = _render(build_pilot_job(_spec(), 1, 0, cfg))
    pod = job["spec"]["template"]["spec"]
    assert [v["name"] for v in pod["volumes"]] == ["sidecar-volume", "generated-code"]
    assert "initContainers" not in pod
    science = _containers(pod)["transformer"]
    assert "proxy-exporter" not in science["args"][0]
    env = _env(science)
    assert "VECTOR_HOST" not in env
    assert "CACHE_PREFIX" not in env


def test_csi_cvmfs_volume_has_no_mount_propagation():
    cfg = _config(cvmfs_volume={"persistentVolumeClaim": {"claimName": "cvmfs"}})
    pod = _render(build_pilot_job(_spec(), 1, 0, cfg))["spec"]["template"]["spec"]
    assert "mountPropagation" not in _mounts(_containers(pod)["sidecar"])["cvmfs"]


def test_volume_destination():
    job = build_pilot_job(_spec(result_destination="volume"), 1, 0, _config())
    pod = _render(job)["spec"]["template"]["spec"]
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["posix-volume"]["emptyDir"] == {}
    env = _env(_containers(pod)["sidecar"])
    assert env["OUTPUT_DIR"] == "/posix_volume/results"
    assert "MINIO_URL" not in env
    assert _mounts(_containers(pod)["sidecar"])["posix-volume"]["mountPath"] == (
        "/posix_volume"
    )

    cfg = _config(persistence_claim="servicex-results")
    pod = _render(build_pilot_job(_spec(result_destination="volume"), 1, 0, cfg))
    volumes = {v["name"]: v for v in pod["spec"]["template"]["spec"]["volumes"]}
    assert volumes["posix-volume"]["persistentVolumeClaim"] == {
        "claimName": "servicex-results"
    }


def test_mount_local_mounts_the_sidecar_source():
    cfg = _config(mount_local=True)
    pod = _render(build_pilot_job(_spec(), 1, 0, cfg))["spec"]["template"]["spec"]
    mounts = _mounts(_containers(pod)["sidecar"])
    assert mounts["host-volume"]["mountPath"] == "/servicex"
    assert mounts["host-scripts-volume"]["mountPath"] == "/servicex/scripts"


def test_vector_is_a_native_sidecar():
    pod = _render(build_pilot_job(_spec(), 1, 0, _config()))["spec"]["template"]["spec"]
    [vector] = pod["initContainers"]
    assert vector["name"] == "vector"
    assert vector["restartPolicy"] == "Always"
    assert vector["image"] == "timberio/vector:0.50.0-debian"
    assert vector["args"] == ["--config", "/etc/vector/vector.yaml"]
    assert vector["resources"] == {"requests": {"cpu": "50m", "memory": "64Mi"}}
    env = _env(vector)
    assert env["REQUEST_ID"] == REQUEST_ID
    assert env["VECTOR_THREADS"] == "2"
    mounts = _mounts(vector)
    assert set(mounts) == {"sidecar-volume", "vector-config", "vector-data"}
    assert mounts["sidecar-volume"]["readOnly"] is True
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["vector-config"]["configMap"] == {
        "name": "servicex-transformer-vector-config"
    }
    # Vector's config isn't mounted into the other containers
    for name in ("sidecar", "transformer"):
        assert "vector-config" not in _mounts(_containers(pod)[name])


def test_custom_sidecar_command():
    cfg = _config(sidecar_command=("python", "-m", "pilot"))
    pod = _render(build_pilot_job(_spec(), 1, 0, cfg))["spec"]["template"]["spec"]
    assert _containers(pod)["sidecar"]["command"] == ["python", "-m", "pilot"]


# ----- backend --------------------------------------------------------------------


def _job_with(*conditions: tuple[str, str]) -> client.V1Job:
    return client.V1Job(
        status=client.V1JobStatus(
            conditions=[client.V1JobCondition(type=t, status=s) for t, s in conditions]
        )
    )


def test_is_live():
    assert is_live(client.V1Job())
    assert is_live(_job_with())
    assert is_live(_job_with(("Suspended", "True")))
    assert is_live(_job_with(("Complete", "False")))
    for terminal in ("Complete", "Failed", "SuccessCriteriaMet", "FailureTarget"):
        assert not is_live(_job_with((terminal, "True")))


class FakeBatch:
    def __init__(self, existing=(), jobs=()):
        self.created = []
        self.existing = set(existing)
        self.jobs = list(jobs)
        self.calls = []

    def create_namespaced_job(self, namespace, body):
        if body.metadata.name in self.existing:
            raise ApiException(status=409, reason="AlreadyExists")
        self.created.append((namespace, body.metadata.name))

    def list_namespaced_job(self, namespace, label_selector):
        self.calls.append(("list", namespace, label_selector))
        return SimpleNamespace(items=self.jobs)

    def delete_collection_namespaced_job(
        self, namespace, label_selector, propagation_policy
    ):
        self.calls.append(("delete", namespace, label_selector, propagation_policy))


class FakeCore:
    def __init__(self, status=None):
        self.status = status
        self.deleted = []

    def delete_namespaced_config_map(self, name, namespace):
        if self.status:
            raise ApiException(status=self.status)
        self.deleted.append((namespace, name))


async def test_launch_creates_one_job_per_pilot():
    batch = FakeBatch()
    backend = KubernetesJobBackend(_config(), batch, FakeCore())
    await backend.launch_pilots(_spec(), 3, 4)
    assert batch.created == [
        ("servicex", f"transformer-{REQUEST_ID}-4-{i}") for i in range(3)
    ]


async def test_relaunch_counts_existing_jobs_as_launched():
    batch = FakeBatch(existing={f"transformer-{REQUEST_ID}-4-0"})
    backend = KubernetesJobBackend(_config(), batch, FakeCore())
    await backend.launch_pilots(_spec(), 2, 4)
    assert batch.created == [("servicex", f"transformer-{REQUEST_ID}-4-1")]


async def test_launch_raises_other_api_errors():
    class Forbidden(FakeBatch):
        def create_namespaced_job(self, namespace, body):
            raise ApiException(status=403, reason="Forbidden")

    backend = KubernetesJobBackend(_config(), Forbidden(), FakeCore())
    with pytest.raises(ApiException):
        await backend.launch_pilots(_spec(), 1, 1)


async def test_count_live_pilots_skips_finished_jobs():
    batch = FakeBatch(
        jobs=[
            _job_with(),
            _job_with(("Complete", "True")),
            _job_with(("Failed", "True")),
            client.V1Job(),
        ]
    )
    backend = KubernetesJobBackend(_config(), batch, FakeCore())
    assert await backend.count_live_pilots(REQUEST_ID) == 2
    assert batch.calls == [("list", "servicex", f"servicex/request-id={REQUEST_ID}")]


async def test_delete_pool_deletes_the_requests_jobs():
    batch = FakeBatch()
    backend = KubernetesJobBackend(_config(), batch, FakeCore())
    await backend.delete_pool(REQUEST_ID)
    assert batch.calls == [
        ("delete", "servicex", f"servicex/request-id={REQUEST_ID}", "Background")
    ]


async def test_cleanup_deletes_jobs_and_config_map():
    batch, core = FakeBatch(), FakeCore()
    backend = KubernetesJobBackend(_config(), batch, core)
    await backend.cleanup_request(REQUEST_ID)
    assert batch.calls[0][0] == "delete"
    assert core.deleted == [("servicex", f"{REQUEST_ID}-generated-source")]


async def test_cleanup_tolerates_a_missing_config_map():
    backend = KubernetesJobBackend(_config(), FakeBatch(), FakeCore(status=404))
    await backend.cleanup_request(REQUEST_ID)
    with pytest.raises(ApiException):
        await KubernetesJobBackend(
            _config(), FakeBatch(), FakeCore(status=500)
        ).cleanup_request(REQUEST_ID)


# ----- backend selection ----------------------------------------------------------


def _settings(**changes) -> Settings:
    return dataclasses.replace(Settings.from_env({}), **changes)


def test_worker_backend_settings():
    assert Settings.from_env({}).worker_backend == "stub"
    settings = Settings.from_env(
        {"WORKER_BACKEND": " Kubernetes ", "TRANSFORMER_CONFIG_FILE": "/etc/t.json"}
    )
    assert settings.worker_backend == "kubernetes"
    assert settings.transformer_config_file == "/etc/t.json"


def test_build_backend_stub():
    assert isinstance(build_backend(_settings()), StubPoolBackend)


def test_build_backend_kubernetes(tmp_path, monkeypatch):
    path = tmp_path / "transformer.json"
    path.write_text(json.dumps(FULL_CONFIG))
    loaded = []
    monkeypatch.setattr(
        "servicex_orchestrator.backends.kubernetes_job.load_kube_config",
        lambda: loaded.append(True),
    )
    backend = build_backend(
        _settings(worker_backend="kubernetes", transformer_config_file=str(path))
    )
    assert isinstance(backend, KubernetesJobBackend)
    assert backend.cfg.namespace == "servicex"
    assert loaded == [True]


def test_build_backend_rejects_bad_settings():
    with pytest.raises(ValueError, match="TRANSFORMER_CONFIG_FILE"):
        build_backend(_settings(worker_backend="kubernetes"))
    with pytest.raises(ValueError, match="Unknown WORKER_BACKEND"):
        build_backend(_settings(worker_backend="condor"))
