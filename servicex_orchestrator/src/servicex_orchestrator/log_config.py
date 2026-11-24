"""Logging for the orchestrator: stdout, plus the release's Vector aggregator.

Records reach Vector as newline-delimited JSON over TCP, shaped like the rows of the
app's `log_messages` table (the same shape as the app's and the transformer sidecar's
VectorFormatter, with `component` = "servicex_orchestrator"). The request page's log
grid selects rows by `request_id`, so every record logged inside a request's
workflows or activities must carry one. RequestContextFilter derives it from the
Temporal context the SDK attaches to `workflow.logger` / `activity.logger` records.
"""

import json
import logging
import os
import queue
import re
import traceback
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener, SocketHandler
from typing import Any, Optional

from temporalio import activity, workflow

COMPONENT = "servicex_orchestrator"

# transform-<request_id>, transform-<request_id>-batch-<n>, pool-<request_id>.
# dataset-<dataset_id> is shared by every request for the dataset, so it has none.
_REQUEST_WORKFLOW_ID = re.compile(
    r"^(?:transform|pool)-(?P<request_id>.+?)(?:-batch-\d+)?$"
)

# Attributes every LogRecord has. Anything else on a record came from `extra=` (or
# from a filter) and goes into the `extra` JSON column.
_STANDARD_ATTRS = set(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None))
) | {"message", "asctime", "taskName"}

# Set by our own filter for the stdout format, not worth shipping.
_LOCAL_ATTRS = {"request_id", "dataset_id", "workflow_id", "context"}


def request_id_from_workflow_id(workflow_id: Optional[str]) -> Optional[str]:
    if not workflow_id:
        return None
    match = _REQUEST_WORKFLOW_ID.match(workflow_id)
    return match.group("request_id") if match else None


class RequestContextFilter(logging.Filter):
    """Stamp `workflow_id`, `request_id` and `dataset_id` onto every record.

    The ids come from, in order: the caller's own `extra=`, then the
    `temporal_workflow` / `temporal_activity` dict the SDK's logger adapters add.
    An activity's dict names the workflow that scheduled it, so a batch's
    transform_file logs are attributed to the request too.

    Attach it to handlers, not loggers: a logger's filters don't see records that
    propagate up from child loggers.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        temporal = getattr(record, "temporal_workflow", None) or getattr(
            record, "temporal_activity", None
        )
        workflow_id = (
            temporal.get("workflow_id") if isinstance(temporal, dict) else None
        )
        record.workflow_id = workflow_id
        if not getattr(record, "request_id", None):
            record.request_id = request_id_from_workflow_id(workflow_id)
        if not hasattr(record, "dataset_id"):
            record.dataset_id = None
        record.context = f" [{workflow_id}]" if workflow_id else ""
        return True


class VectorFormatter(logging.Formatter):
    """One `log_messages` row as JSON. Non-standard record attributes go under `extra`."""

    def __init__(self, instance: str):
        super().__init__()
        self.instance = instance

    def format(self, record: logging.LogRecord) -> str:
        extra = {
            key: value
            for key, value in vars(record).items()
            if key not in _STANDARD_ATTRS and key not in _LOCAL_ATTRS
        }
        if record.exc_info:
            extra["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))
            extra["lineno"] = record.lineno
            extra["funcName"] = record.funcName
        message = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "instance": self.instance,
            "component": COMPONENT,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "dataset_id": getattr(record, "dataset_id", None),
            "extra": extra,
        }
        return json.dumps(message, default=str)


class JsonLinesSocketHandler(SocketHandler):
    """Send each formatted record as one line over TCP (what Vector's socket source
    with the json codec reads). Reconnects with backoff if the aggregator restarts;
    records logged while it is down are dropped rather than blocking."""

    def makePickle(self, record: logging.LogRecord) -> bytes:
        return self.format(record).encode("utf-8") + b"\n"


class _DirectQueueHandler(QueueHandler):
    """Put the record on the queue as-is.

    The stdlib's prepare() formats and copies the record so it can cross a process
    boundary, and nulls exc_info on the way. The listener is a thread in this
    process, so that buys nothing, and keeping exc_info is what lets tracebacks
    reach the `extra` column.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


def configure_logging(
    level: str,
    vector_host: Optional[str] = None,
    vector_port: Optional[int] = None,
    instance: Optional[str] = None,
) -> Optional[QueueListener]:
    """Set up stdout logging and, if a Vector address is given, shipping to Vector.

    Returns the Vector QueueListener (already started) so the caller can stop it,
    flushing what is queued, on shutdown.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    context = RequestContextFilter()
    stream = logging.StreamHandler()
    stream.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s%(context)s: %(message)s")
    )
    stream.addFilter(context)
    root.addHandler(stream)

    # The workflow/activity details go on the record (and so into `extra`) and the
    # workflow id into the stdout format; don't also append them to every message.
    workflow.logger.workflow_info_on_message = False
    activity.logger.activity_info_on_message = False

    if not (vector_host and vector_port):
        return None

    vector = JsonLinesSocketHandler(vector_host, int(vector_port))
    vector.setFormatter(
        VectorFormatter(instance or os.environ.get("INSTANCE_NAME", "Unknown"))
    )

    # The socket write happens on the listener's thread, so logging never blocks
    # the worker's event loop (or a workflow task) on the network.
    log_queue: "queue.Queue[Any]" = queue.Queue(-1)
    queued = _DirectQueueHandler(log_queue)
    # Filter on the producing thread, while the Temporal context is still current.
    queued.addFilter(context)
    root.addHandler(queued)

    listener = QueueListener(log_queue, vector, respect_handler_level=True)
    listener.start()
    return listener
