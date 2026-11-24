"""Dataset lookups end to end on a real Postgres: the real app's PUT files endpoint,
the real orchestrator worker and the real DIDFinderWorker (with a fake catalog,
fake_finder.py). Transforms are still stubs.

Run it with scripts/lookup-e2e-test.sh, which sets up the database and the env:
CONTRACT_ADMIN_URL, CONTRACT_ORCHESTRATOR_URL, E2E_APP_DIR (servicex_app) and
DID_FINDER_LIB_DIR (a ServiceX_DID_Finder_lib checkout with its poetry env).
"""

import contextlib
import os
import pathlib
import platform
import socket
import subprocess
import sys
import time
import uuid

import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment

from pg_seed import ADMIN_URL, ORCHESTRATOR_URL, Seeder, engine
from servicex_orchestrator.config import Settings
from servicex_orchestrator.models import (
    REQUEST_COMPLETE,
    TransformRequestInput,
    TransformRequestTuning,
)
from servicex_orchestrator.worker import build_worker
from servicex_orchestrator.workflows import TransformRequestWorkflow

APP_DIR = os.environ.get("E2E_APP_DIR")
LIB_DIR = os.environ.get("DID_FINDER_LIB_DIR")
FAKE_FINDER = pathlib.Path(__file__).with_name("fake_finder.py")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not (ADMIN_URL and ORCHESTRATOR_URL and APP_DIR and LIB_DIR),
        reason="run scripts/lookup-e2e-test.sh",
    ),
    pytest.mark.asyncio(loop_scope="module"),
]

FILE_SIZE = 1000
FILE_EVENTS = 10


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, process: subprocess.Popen, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{process.args} exited with {process.returncode}")
        with contextlib.suppress(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return
        time.sleep(0.5)
    raise TimeoutError(f"nothing listening on {port}")


def _native(args: list[str]) -> list[str]:
    """On an Apple Silicon Mac, a Python running under Rosetta starts its children as
    x86_64 too, which breaks another venv built for arm64. Run them natively."""
    if sys.platform == "darwin" and platform.machine() == "x86_64":
        translated = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True
        ).stdout.strip()
        if translated == "1":
            return ["arch", "-arm64", *args]
    return args


def _wait_for_log(log: pathlib.Path, text: str, process, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if log.exists() and text in log.read_text():
            return
        if process.poll() is not None:
            raise RuntimeError(f"{process.args} exited:\n{log.read_text()}")
        time.sleep(0.5)
    raise TimeoutError(f"no {text!r} in {log}:\n{log.read_text()}")


@contextlib.contextmanager
def _process(args, cwd, env, log: pathlib.Path):
    with open(log, "w") as out:
        process = subprocess.Popen(
            args, cwd=cwd, env={**os.environ, **env}, stdout=out, stderr=out
        )
        try:
            yield process
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("e2e")


@pytest.fixture(scope="module")
def app_endpoint(state_dir):
    """The real ServiceX app, in Temporal mode, on the e2e Postgres."""
    port = _free_port()
    env = {
        "APP_CONFIG_FILE": f"{APP_DIR}/servicex_app_test/test.config",
        "SQLALCHEMY_DATABASE_URI": ADMIN_URL,
        "ALLOWED_IMAGE_PREFIXES": '["sslhep/"]',
        "FLASK_APP": "servicex_app/app.py",
        "ORCHESTRATOR": "temporal",
    }
    args = ["poetry", "run", "flask", "run", "--port", str(port), "--no-reload"]
    with _process(args, APP_DIR, env, state_dir / "app.log") as app:
        _wait_for_port(port, app)
        yield f"http://127.0.0.1:{port}/servicex/internal/transformation/"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def temporal():
    async with await WorkflowEnvironment.start_local() as env:
        yield env


@pytest.fixture(scope="module")
def finder(temporal, app_endpoint, state_dir):
    """The fake catalog behind the real DIDFinderWorker, in the lib's poetry env."""
    env = {
        "TEMPORAL_ADDRESS": temporal.client.service_client.config.target_host,
        "SERVICEX_INTERNAL_ENDPOINT": app_endpoint,
        "E2E_STATE_DIR": str(state_dir),
    }
    args = _native(["poetry", "run", "python", str(FAKE_FINDER)])
    log = state_dir / "finder.log"
    with _process(args, LIB_DIR, env, log) as process:
        _wait_for_log(log, "polling task queue", process)
        yield state_dir / "lookups.log"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def task_queue(temporal):
    """The orchestrator worker, with its real DB activities as its own role."""
    orchestrator = engine(ORCHESTRATOR_URL)
    settings = Settings(
        temporal_address=temporal.client.service_client.config.target_host,
        temporal_namespace=temporal.client.namespace,
        task_queue=f"e2e-{uuid.uuid4()}",
        log_level="INFO",
        stub_activity_delay_seconds=0.0,
    )
    async with build_worker(temporal.client, settings, orchestrator):
        yield settings.task_queue
    await orchestrator.dispose()


@pytest_asyncio.fixture(loop_scope="module")
async def seed():
    admin = engine(ADMIN_URL)
    seeder = Seeder(admin)
    yield seeder
    await seeder.cleanup()
    await admin.dispose()


async def _run(temporal, task_queue, request_id, dataset_id, did):
    return await temporal.client.execute_workflow(
        TransformRequestWorkflow.run,
        TransformRequestInput(
            request_id=request_id,
            did=f"rucio://{did}",
            did_scheme="rucio",
            dataset_id=dataset_id,
            image="img",
            generated_code_cm="cm",
            transformer_language="python",
            transformer_command="cmd",
            result_destination="object-store",
            result_format="parquet",
            max_workers=2,
            tuning=TransformRequestTuning(batch_size=50, pool_reconcile_seconds=1),
        ),
        id=f"transform-{request_id}",
        task_queue=task_queue,
    )


def _lookups(log: pathlib.Path, dataset_id: int) -> int:
    if not log.exists():
        return 0
    lines = log.read_text().splitlines()
    return sum(1 for line in lines if line.split()[0] == str(dataset_id))


async def _dataset(seed, dataset_id):
    return await seed.row(
        "SELECT d.lookup_status, d.n_files, d.size, d.events, "
        "(SELECT count(*) FROM files f WHERE f.dataset_id = d.id) AS rows, "
        "(SELECT count(DISTINCT file_key) FROM files f WHERE f.dataset_id = d.id) "
        "AS keys FROM datasets d WHERE d.id = :d",
        d=dataset_id,
    )


async def _request(seed, request_id):
    return await seed.row(
        "SELECT status, files FROM requests WHERE request_id = :r", r=request_id
    )


def _complete(n):
    return ("complete", n, n * FILE_SIZE, n * FILE_EVENTS, n, n)


async def test_lookup_twice_then_cache_hit(temporal, task_queue, finder, seed):
    did = "e2e:twice-10"
    dataset_id = await seed.dataset("looking")

    first = await seed.request(dataset_id, status="lookup")
    result = await _run(temporal, task_queue, first, dataset_id, did)
    assert result.status == REQUEST_COMPLETE
    assert tuple(await _dataset(seed, dataset_id)) == _complete(10)
    assert tuple(await _request(seed, first)) == ("running", 10)
    assert _lookups(finder, dataset_id) == 1

    # The lookup runs again on the same row (as after a failed lookup, which submit
    # marks `looking` again): the files are upserted, not duplicated.
    await seed.execute(
        "UPDATE datasets SET lookup_status = 'looking' WHERE id = :d", d=dataset_id
    )
    again = await seed.request(dataset_id, status="lookup")
    result = await _run(temporal, task_queue, again, dataset_id, did)
    assert result.status == REQUEST_COMPLETE
    assert _lookups(finder, dataset_id) == 2
    assert tuple(await _dataset(seed, dataset_id)) == _complete(10)

    # A request for the complete dataset (submit marks it running) skips the lookup.
    cached = await seed.request(dataset_id, status="running")
    result = await _run(temporal, task_queue, cached, dataset_id, did)
    assert result.status == REQUEST_COMPLETE
    assert _lookups(finder, dataset_id) == 2
    assert tuple(await _request(seed, cached)) == ("running", 10)


async def test_forced_retry_leaves_no_duplicates(temporal, task_queue, finder, seed):
    dataset_id = await seed.dataset("looking")
    request_id = await seed.request(dataset_id, status="lookup")

    result = await _run(
        temporal, task_queue, request_id, dataset_id, "e2e:retry-12-failonce"
    )

    assert result.status == REQUEST_COMPLETE
    assert _lookups(finder, dataset_id) == 2, "the first attempt fails and is retried"
    assert tuple(await _dataset(seed, dataset_id)) == _complete(12)
    assert tuple(await _request(seed, request_id)) == ("running", 12)
