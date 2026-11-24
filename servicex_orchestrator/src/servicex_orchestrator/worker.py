import asyncio
import contextlib
import logging
import signal
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Optional

from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker
from sqlalchemy.ext.asyncio import AsyncEngine

from servicex_orchestrator import db
from servicex_orchestrator.activities import build_activities, build_stubs
from servicex_orchestrator.config import Settings, did_finder_task_queue
from servicex_orchestrator.log_config import configure_logging
from servicex_orchestrator.workflows import WORKFLOWS

logger = logging.getLogger(__name__)

MAX_CONNECT_BACKOFF_SECONDS = 30.0


async def connect(settings: Settings) -> Client:
    """Connect to the Temporal frontend, waiting until it and our namespace exist.

    On a fresh install the frontend comes up after the schema Job finishes and the
    namespace is created by a separate Job after that, so keep retrying instead of
    crash-looping the pod.
    """
    backoff = 1.0
    while True:
        try:
            client = await Client.connect(
                settings.temporal_address, namespace=settings.temporal_namespace
            )
            await client.workflow_service.describe_namespace(
                DescribeNamespaceRequest(namespace=settings.temporal_namespace)
            )
            return client
        except RuntimeError as err:
            # Client.connect raises RuntimeError when the frontend is unreachable.
            logger.warning(
                "Temporal frontend %s not reachable yet: %s",
                settings.temporal_address,
                err,
            )
        except RPCError as err:
            if err.status == RPCStatusCode.NOT_FOUND:
                logger.warning(
                    "Temporal namespace %r does not exist yet",
                    settings.temporal_namespace,
                )
            elif err.status == RPCStatusCode.UNAVAILABLE:
                logger.warning("Temporal frontend unavailable: %s", err)
            else:
                raise
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_CONNECT_BACKOFF_SECONDS)


GRACEFUL_SHUTDOWN = timedelta(seconds=20)


def build_worker(
    client: Client, settings: Settings, engine: Optional[AsyncEngine] = None
) -> Worker:
    return Worker(
        client,
        task_queue=settings.task_queue,
        workflows=WORKFLOWS,
        activities=build_activities(settings, engine),
        graceful_shutdown_timeout=GRACEFUL_SHUTDOWN,
    )


def build_stub_did_finder_worker(
    client: Client, settings: Settings, scheme: str
) -> Worker:
    """Serves the stub `lookup_dataset` where no real DID finder for `scheme` runs."""
    return Worker(
        client,
        task_queue=did_finder_task_queue(scheme),
        activities=build_stubs(settings).did_finder(),
        graceful_shutdown_timeout=GRACEFUL_SHUTDOWN,
    )


def build_workers(
    client: Client, settings: Settings, engine: Optional[AsyncEngine] = None
) -> list[Worker]:
    """The orchestrator worker, then one stub DID finder per configured scheme."""
    return [
        build_worker(client, settings, engine),
        *(
            build_stub_did_finder_worker(client, settings, scheme)
            for scheme in settings.stub_did_finder_schemes
        ),
    ]


@contextlib.asynccontextmanager
async def running(workers: list[Worker]) -> AsyncIterator[list[Worker]]:
    """Run the workers for the duration of the block, then shut them down together.

    If any worker fails fatally, the block is canceled and that error is raised.
    """
    async with contextlib.AsyncExitStack() as stack:
        for worker in workers:
            await stack.enter_async_context(worker)
        try:
            yield workers
        finally:
            # Drain in parallel; the exit stack's own shutdowns then return at once.
            await asyncio.gather(*(worker.shutdown() for worker in workers))


async def open_database(settings: Settings) -> Optional[AsyncEngine]:
    """The Postgres pool, checked against the schema and grants we expect.

    Raises db.DatabaseUnavailable or db.SchemaMismatch, which end the process: the
    pod restarts with backoff, and on a fresh install the check passes once the app
    has migrated the database and created our role.
    """
    if not settings.database_url:
        logger.warning(
            "DATABASE_URL is not set: running without the ServiceX database "
            "(fine while every DB activity is a stub)"
        )
        return None
    engine = db.create_engine(settings)
    try:
        revision = await db.startup_check(engine)
    except BaseException:
        await engine.dispose()
        raise
    logger.info(
        "Connected to Postgres %s (schema revision %s, pool %d+%d)",
        db.describe(engine),
        revision,
        settings.db_pool_size,
        settings.db_max_overflow,
    )
    return engine


async def run(settings: Settings) -> None:
    engine = await open_database(settings)
    try:
        await _run(settings, engine)
    finally:
        if engine is not None:
            await engine.dispose()


async def _run(settings: Settings, engine: Optional[AsyncEngine]) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # Still waiting on Temporal when the pod is stopped: exit now, don't sit out the
    # termination grace period.
    connecting = asyncio.create_task(connect(settings))
    stopping = asyncio.create_task(stop.wait())
    await asyncio.wait({connecting, stopping}, return_when=asyncio.FIRST_COMPLETED)
    if not connecting.done():
        connecting.cancel()
        logger.info("Shutdown requested before Temporal was reachable")
        return
    stopping.cancel()
    client = connecting.result()

    workers = build_workers(client, settings, engine)
    logger.info(
        "Polling task queues %s in namespace %r at %s",
        ", ".join(repr(worker.task_queue) for worker in workers),
        settings.temporal_namespace,
        settings.temporal_address,
    )
    if settings.stub_did_finder_schemes:
        logger.warning(
            "Serving STUB dataset lookups for DID schemes %s",
            ", ".join(settings.stub_did_finder_schemes),
        )
    async with running(workers):
        await stop.wait()
        logger.info("Shutdown requested, draining in-flight tasks")


def main() -> None:
    settings = Settings.from_env()
    vector = configure_logging(
        settings.log_level,
        vector_host=settings.vector_host,
        vector_port=settings.vector_port,
        instance=settings.instance_name,
    )
    if vector:
        logger.info(
            "Shipping logs to Vector at %s:%s",
            settings.vector_host,
            settings.vector_port,
        )
    try:
        asyncio.run(run(settings))
    except (db.DatabaseUnavailable, db.SchemaMismatch) as err:
        logger.critical("Orchestrator database check failed: %s", err)
        raise SystemExit(1) from None
    finally:
        if vector:
            vector.stop()  # flushes what is still queued
            for handler in vector.handlers:
                handler.close()


if __name__ == "__main__":
    main()
