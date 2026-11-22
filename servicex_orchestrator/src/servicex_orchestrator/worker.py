import asyncio
import logging
import signal
from datetime import timedelta

from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

from servicex_orchestrator.activities import ACTIVITIES
from servicex_orchestrator.config import Settings
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


def build_worker(client: Client, settings: Settings) -> Worker:
    return Worker(
        client,
        task_queue=settings.task_queue,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        graceful_shutdown_timeout=timedelta(seconds=20),
    )


async def run(settings: Settings) -> None:
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

    logger.info(
        "Polling task queue %r in namespace %r at %s",
        settings.task_queue,
        settings.temporal_namespace,
        settings.temporal_address,
    )
    async with build_worker(client, settings):
        await stop.wait()
        logger.info("Shutdown requested, draining in-flight tasks")


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
