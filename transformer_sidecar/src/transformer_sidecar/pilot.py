# Copyright (c) 2026, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""The transformer sidecar as a Temporal pilot.

The orchestrator's PoolManagerWorkflow launches each pilot as a single-pod
Kubernetes Job. The pilot polls the request's `transform-<request_id>` task queue for
`transform_file`, one file at a time, and exits 0 once it has had no file for
WORKER_IDLE_TIMEOUT_SECONDS, so the pool shrinks by itself and no pod is killed in the
middle of a file (plan §4.4, §5.2). The result of each file goes back to the
orchestrator as the activity's return value or error: the pilot makes no calls to the
ServiceX app.

Its settings come from the environment (the "pilot contract" in the orchestrator's
README): TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE, REQUEST_ID,
RESULT_DESTINATION, RESULT_FORMAT, SHARED_DIR, OUTPUT_DIR and
WORKER_IDLE_TIMEOUT_SECONDS; plus the MINIO_* settings for the object store.
"""

import asyncio
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping, Optional

from temporalio import activity
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

from transformer_sidecar.file_transformer import (
    OBJECT_STORE_DEST,
    FileTransformer,
    PublishError,
)
from transformer_sidecar.object_store_manager import ObjectStoreManager
from transformer_sidecar.science_container_command import (
    ScienceContainerCommand,
    ScienceContainerException,
)
from transformer_sidecar.temporal_models import (
    FILE_FAILED,
    FILE_SUCCESS,
    TRANSFORM_ACTIVITY_NAME,
    TRANSIENT_IO,
    FileResult,
    TransformFileInput,
)
from transformer_sidecar.transform_helpers import (
    get_process_info,
    read_capabilities_file,
)
from transformer_sidecar.transformer_logging import initialize_logging, set_request_id
from transformer_sidecar.transformer_logging.stream_formatter import StreamFormatter

# By name: run as a script, __name__ is __main__
logger = logging.getLogger("transformer_sidecar.pilot")

# The orchestrator's heartbeat_timeout for transform_file is 3 minutes
HEARTBEAT_INTERVAL_SECONDS = 30.0
# Failure details travel in the workflow history: keep the end of the log only
MAX_LOG_BODY_CHARS = 32_000
MAX_CONNECT_BACKOFF_SECONDS = 30.0
# The scripts the science container runs, copied into the shared volume. Relative to
# the working directory, as in transformer.py: /servicex in the image.
SCRIPTS_DIR = "scripts"
SCRIPTS = ("watch.sh", "proxy-exporter.sh")

PLACE = {
    "host": os.getenv("HOST_NAME", "unknown"),
    "site": os.getenv("site", "unknown"),
    "pod": os.getenv("POD_NAME", "unknown"),
}

EXIT_OK = 0
# The science container is gone. The Job fails; the file it held is retried by
# Temporal on another pilot, and the pool manager replaces this one.
EXIT_BROKEN = 1


@dataclass(frozen=True)
class PilotSettings:
    request_id: str
    result_destination: str
    result_format: str
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = ""
    shared_dir: str = "/servicex/output"
    # Where the volume destination writes the output files
    output_dir: Optional[str] = None
    idle_timeout_seconds: float = 120.0
    # How long a stopping pilot lets its file finish. Keep it under the pod's
    # terminationGracePeriodSeconds (30 s by default).
    graceful_shutdown_seconds: float = 25.0

    def __post_init__(self):
        if not self.task_queue:
            object.__setattr__(self, "task_queue", f"transform-{self.request_id}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "PilotSettings":
        missing = [
            name
            for name in ("REQUEST_ID", "RESULT_DESTINATION", "RESULT_FORMAT")
            if not env.get(name)
        ]
        if missing:
            raise ValueError(f"The pilot needs {', '.join(missing)} in its environment")
        return cls(
            request_id=env["REQUEST_ID"],
            result_destination=env["RESULT_DESTINATION"],
            result_format=env["RESULT_FORMAT"],
            temporal_address=env.get("TEMPORAL_ADDRESS") or "localhost:7233",
            temporal_namespace=env.get("TEMPORAL_NAMESPACE") or "default",
            task_queue=env.get("TEMPORAL_TASK_QUEUE") or "",
            shared_dir=env.get("SHARED_DIR") or "/servicex/output",
            output_dir=env.get("OUTPUT_DIR") or None,
            idle_timeout_seconds=float(env.get("WORKER_IDLE_TIMEOUT_SECONDS") or 120),
            graceful_shutdown_seconds=float(
                env.get("WORKER_GRACEFUL_SHUTDOWN_SECONDS") or 25
            ),
        )


class TransformActivity:
    """The transform_file activity, bound to the pilot's FileTransformer.

    It also keeps what the pilot's idle check needs: files in flight, when the last
    one ended, and whether the science container broke.
    """

    def __init__(
        self,
        transformer: FileTransformer,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
    ):
        self.transformer = transformer
        self.heartbeat_interval = heartbeat_interval
        self.in_flight = 0
        self.last_finished = time.monotonic()
        self.broken = asyncio.Event()

    @activity.defn(name=TRANSFORM_ACTIVITY_NAME)
    async def transform_file(self, input: TransformFileInput) -> FileResult:
        """Transform one file and return its result.

        Every replica failing is a non-retryable FileFailed carrying the science log;
        an output that couldn't be written, or a science container that is gone, is a
        retryable TransientIO. Anything unexpected propagates, and is retried.
        """
        self.in_flight += 1
        try:
            return await self._transform(input)
        finally:
            self.in_flight -= 1
            self.last_finished = time.monotonic()

    async def _transform(self, input: TransformFileInput) -> FileResult:
        info = activity.info()
        if input.spec.request_id != self.transformer.request_id:
            # Can't happen: the queue is the request's own. Let another pilot take it.
            raise ApplicationError(
                f"Pilot for request {self.transformer.request_id} got a file of "
                f"request {input.spec.request_id}",
                type=TRANSIENT_IO,
            )
        logger.info(
            f"Transforming file {input.file.file_id} (attempt {info.attempt})",
            extra={"file_id": input.file.file_id, "place": PLACE},
        )

        keepalive = asyncio.create_task(self._keepalive())
        try:
            outcome = await asyncio.to_thread(self.transformer.transform, input.file)
        except ScienceContainerException as err:
            logger.exception(
                "Science container not responding. Shutting down this pilot.",
                extra={"file_id": input.file.file_id},
            )
            self.broken.set()
            raise ApplicationError(
                f"Science container not responding: {err}", type=TRANSIENT_IO
            ) from err
        except PublishError as err:
            raise ApplicationError(str(err), type=TRANSIENT_IO) from err
        finally:
            keepalive.cancel()

        if not outcome.success:
            raise ApplicationError(
                outcome.error_info,
                {
                    "error_info": outcome.error_info,
                    "log_body": outcome.log_body[-MAX_LOG_BODY_CHARS:],
                    "replica": outcome.replica_used,
                },
                type=FILE_FAILED,
                non_retryable=True,
            )
        return FileResult(
            file_id=input.file.file_id,
            status=FILE_SUCCESS,
            object_name=outcome.object_name,
            replica_used=outcome.replica_used,
            events=outcome.events,
            bytes=outcome.bytes,
            transform_seconds=outcome.seconds,
        )

    async def _keepalive(self) -> None:
        """Heartbeat while the transform runs in its thread. This is what tells
        Temporal the pilot is alive, and lets a cancellation reach the activity."""
        while True:
            activity.heartbeat()
            await asyncio.sleep(self.heartbeat_interval)


class Pilot:
    """Polls the task queue until idle, stopped, or the science container breaks."""

    def __init__(
        self,
        settings: PilotSettings,
        transform: TransformActivity,
        poll_interval: float = 1.0,
    ):
        self.settings = settings
        self.transform = transform
        self.poll_interval = poll_interval

    def build_worker(self, client: Client) -> Worker:
        return Worker(
            client,
            task_queue=self.settings.task_queue,
            activities=[self.transform.transform_file],
            # The science container takes one file at a time
            max_concurrent_activities=1,
            graceful_shutdown_timeout=timedelta(
                seconds=self.settings.graceful_shutdown_seconds
            ),
        )

    async def run(self, client: Client, stop: asyncio.Event) -> int:
        """Serve the queue; return the process exit code."""
        logger.info(
            f"Pilot polling task queue {self.settings.task_queue!r} in namespace "
            f"{self.settings.temporal_namespace!r} at {self.settings.temporal_address}",
            extra={"place": PLACE},
        )
        # Leaving the block shuts the worker down: polling stops, and a file in
        # flight gets graceful_shutdown_seconds to finish.
        async with self.build_worker(client):
            reason = await self._wait_until_done(stop)
            logger.info(f"Pilot stopping: {reason}", extra={"place": PLACE})
        return EXIT_BROKEN if self.transform.broken.is_set() else EXIT_OK

    async def _wait_until_done(self, stop: asyncio.Event) -> str:
        idle_timeout = self.settings.idle_timeout_seconds
        while True:
            if stop.is_set():
                return "shutdown requested"
            if self.transform.broken.is_set():
                return "the science container is not responding"
            idle = time.monotonic() - self.transform.last_finished
            if self.transform.in_flight == 0 and idle >= idle_timeout:
                return f"no file for {idle:.0f}s"
            try:
                await asyncio.wait_for(stop.wait(), self.poll_interval)
            except asyncio.TimeoutError:
                pass


async def connect(settings: PilotSettings, stop: asyncio.Event) -> Optional[Client]:
    """Connect to Temporal, waiting until the frontend and namespace exist. None if
    stop is set first."""
    backoff = 1.0
    while not stop.is_set():
        try:
            client = await Client.connect(
                settings.temporal_address, namespace=settings.temporal_namespace
            )
            await client.workflow_service.describe_namespace(
                DescribeNamespaceRequest(namespace=settings.temporal_namespace)
            )
            return client
        except RuntimeError as err:
            # Client.connect raises RuntimeError when the frontend is unreachable
            logger.warning(
                f"Temporal frontend {settings.temporal_address} not reachable yet: {err}"
            )
        except RPCError as err:
            if err.status == RPCStatusCode.NOT_FOUND:
                logger.warning(
                    f"Temporal namespace {settings.temporal_namespace!r} "
                    "does not exist yet"
                )
            elif err.status == RPCStatusCode.UNAVAILABLE:
                logger.warning(f"Temporal frontend unavailable: {err}")
            else:
                raise
        try:
            await asyncio.wait_for(stop.wait(), backoff)
        except asyncio.TimeoutError:
            pass
        backoff = min(backoff * 2, MAX_CONNECT_BACKOFF_SECONDS)
    return None


def start_transformer(settings: PilotSettings) -> FileTransformer:
    """Get the pod ready, as transformer.init does for Celery: share the scripts with
    the science container, wait for its capabilities file, and accept its connection.
    Blocks until the science container connects."""
    os.makedirs(settings.shared_dir, exist_ok=True)
    scripts_path = os.path.join(settings.shared_dir, "scripts")
    os.makedirs(scripts_path, exist_ok=True)
    for script in SCRIPTS:
        shutil.copy(os.path.join(SCRIPTS_DIR, script), scripts_path)

    capabilities = read_capabilities_file(settings.shared_dir)
    object_store = (
        ObjectStoreManager()
        if settings.result_destination == OBJECT_STORE_DEST
        else None
    )
    startup = get_process_info()
    logger.info(
        "Startup finished.",
        extra={
            "user": startup.user,
            "sys": startup.system,
            "iowait": startup.iowait,
            "place": PLACE,
        },
    )
    science_container = ScienceContainerCommand(request_id=settings.request_id)
    logger.debug("Connected to science container", extra={"place": PLACE})
    return FileTransformer(
        request_id=settings.request_id,
        shared_dir=settings.shared_dir,
        result_destination=settings.result_destination,
        result_format=settings.result_format,
        capabilities=capabilities,
        science_container=science_container,
        object_store=object_store,
        output_dir=settings.output_dir,
    )


async def serve(settings: PilotSettings, transformer: FileTransformer) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    client = await connect(settings, stop)
    if client is None:
        logger.info("Shutdown requested before Temporal was reachable")
        return EXIT_OK
    return await Pilot(settings, TransformActivity(transformer)).run(client, stop)


def stop_science_container(transformer: FileTransformer) -> None:
    """Send `stop.` so watch.sh exits and the science container ends with the Job."""
    try:
        transformer.science_container.close()
    except OSError as err:
        logger.warning(f"Could not stop the science container cleanly: {err}")


def init_logging(request_id: str) -> None:
    # Stamps the id onto every record, including the Temporal SDK's own
    set_request_id(request_id)
    root = initialize_logging()
    # initialize_logging's basicConfig leaves a plain stdout handler on the root
    # logger next to its own formatted one, which would print every line twice.
    # (Celery replaces the root handlers itself; the pilot has to.)
    for handler in list(root.handlers):
        if type(handler) is logging.StreamHandler and not isinstance(
            handler.formatter, StreamFormatter
        ):
            root.removeHandler(handler)


def main() -> int:
    settings = PilotSettings.from_env()
    init_logging(settings.request_id)

    # Before the event loop, SIGTERM keeps its default: the pod just ends.
    transformer = start_transformer(settings)
    try:
        return asyncio.run(serve(settings, transformer))
    finally:
        stop_science_container(transformer)
        logger.info("Pilot exiting", extra={"place": PLACE})


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
