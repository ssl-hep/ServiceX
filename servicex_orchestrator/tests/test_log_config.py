import json
import logging
import socketserver
import sys
import threading
import uuid

import pytest
from temporalio import activity, workflow
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from servicex_orchestrator.activities import StubActivities, ping
from servicex_orchestrator.config import did_finder_task_queue
from servicex_orchestrator.log_config import (
    COMPONENT,
    RequestContextFilter,
    VectorFormatter,
    configure_logging,
    request_id_from_workflow_id,
)
from servicex_orchestrator.models import TransformRequestInput, TransformRequestTuning
from servicex_orchestrator.workflows import WORKFLOWS, TransformRequestWorkflow

REQUEST_ID = "e13936e7-8a21-433e-8ff3-03c034335528"


@pytest.mark.parametrize(
    "workflow_id, expected",
    [
        (f"transform-{REQUEST_ID}", REQUEST_ID),
        (f"transform-{REQUEST_ID}-batch-12", REQUEST_ID),
        (f"pool-{REQUEST_ID}", REQUEST_ID),
        ("dataset-03abbf65", None),
        ("ping-1", None),
        (None, None),
    ],
)
def test_request_id_from_workflow_id(workflow_id, expected):
    assert request_id_from_workflow_id(workflow_id) == expected


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        "temporalio.workflow", logging.INFO, __file__, 1, "hello %s", ("world",), None
    )
    record.__dict__.update(extra)
    return record


def test_filter_uses_workflow_context():
    record = _record(temporal_workflow={"workflow_id": f"pool-{REQUEST_ID}"})
    RequestContextFilter().filter(record)
    assert record.request_id == REQUEST_ID
    assert record.dataset_id is None
    assert record.context == f" [pool-{REQUEST_ID}]"


def test_filter_attributes_activity_to_scheduling_workflow():
    record = _record(
        temporal_activity={
            "activity_type": "transform_file",
            "workflow_id": f"transform-{REQUEST_ID}-batch-3",
        }
    )
    RequestContextFilter().filter(record)
    assert record.request_id == REQUEST_ID


def test_filter_keeps_explicit_ids():
    record = _record(
        request_id="explicit",
        temporal_workflow={"workflow_id": f"transform-{REQUEST_ID}"},
    )
    RequestContextFilter().filter(record)
    assert record.request_id == "explicit"

    lookup = _record(dataset_id=42, temporal_workflow={"workflow_id": "dataset-abc"})
    RequestContextFilter().filter(lookup)
    assert (lookup.request_id, lookup.dataset_id) == (None, 42)


def test_filter_leaves_plain_records_unattributed():
    record = _record()
    RequestContextFilter().filter(record)
    assert (record.request_id, record.dataset_id, record.context) == (None, None, "")


def test_vector_formatter_matches_log_messages_columns():
    record = _record(temporal_workflow={"workflow_id": f"transform-{REQUEST_ID}"})
    RequestContextFilter().filter(record)
    row = json.loads(VectorFormatter("servicex-ben").format(record))

    assert set(row) == {
        "timestamp",
        "level",
        "logger",
        "instance",
        "component",
        "message",
        "request_id",
        "dataset_id",
        "extra",
    }
    assert row["timestamp"].endswith("Z")
    assert row["level"] == "INFO"
    assert row["logger"] == "temporalio.workflow"
    assert row["instance"] == "servicex-ben"
    assert row["component"] == COMPONENT
    assert row["message"] == "hello world"
    assert row["request_id"] == REQUEST_ID
    assert row["dataset_id"] is None
    # The Temporal context rides along; our own bookkeeping attributes don't.
    assert row["extra"] == {
        "temporal_workflow": {"workflow_id": f"transform-{REQUEST_ID}"}
    }


def test_vector_formatter_includes_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record()
        record.exc_info = sys.exc_info()
    row = json.loads(VectorFormatter("x").format(record))
    assert "ValueError: boom" in row["extra"]["stack_trace"]


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    wf_on_message = workflow.logger.workflow_info_on_message
    act_on_message = activity.logger.activity_info_on_message
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)
    workflow.logger.workflow_info_on_message = wf_on_message
    activity.logger.activity_info_on_message = act_on_message


def test_configure_logging_ships_json_lines_to_vector(restore_logging):
    lines: list[bytes] = []
    received = threading.Event()

    class Collector(socketserver.StreamRequestHandler):
        def handle(self):
            for line in self.rfile:
                lines.append(line)
                received.set()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    with Server(("127.0.0.1", 0), Collector) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        listener = configure_logging(
            "INFO",
            vector_host="127.0.0.1",
            vector_port=server.server_address[1],
            instance="servicex-test",
        )
        assert listener is not None
        # The Temporal SDK's activity logger attaches temporal_activity itself.
        logging.getLogger("temporalio.activity").handle(
            _record(temporal_activity={"workflow_id": f"pool-{REQUEST_ID}"})
        )
        logging.getLogger("servicex_orchestrator.test").debug("below the level")
        listener.stop()  # flushes the queue
        for handler in listener.handlers:
            handler.close()
        assert received.wait(5)
        server.shutdown()

    [row] = [json.loads(line) for line in lines]
    assert row["message"] == "hello world"
    assert row["request_id"] == REQUEST_ID
    assert row["instance"] == "servicex-test"
    assert row["component"] == COMPONENT


def test_configure_logging_without_vector_is_stdout_only(restore_logging):
    assert configure_logging("INFO") is None
    assert [type(h) for h in logging.getLogger().handlers] == [logging.StreamHandler]


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.addFilter(RequestContextFilter())

    def emit(self, record):
        self.records.append(record)


async def test_every_request_record_carries_its_request_id(restore_logging):
    """Run a stubbed request and check what the dashboard would see."""
    capture = _Capture()
    root = logging.getLogger()
    root.addHandler(capture)
    root.setLevel(logging.INFO)

    request_id = str(uuid.uuid4())
    stubs = StubActivities(stub_files=7, stub_delay=0)
    task_queue = f"test-{uuid.uuid4()}"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with (
            Worker(
                env.client,
                task_queue=task_queue,
                workflows=WORKFLOWS,
                activities=[ping, *stubs.all()],
            ),
            Worker(
                env.client,
                task_queue=did_finder_task_queue("rucio"),
                activities=stubs.did_finder(),
            ),
        ):
            await env.client.execute_workflow(
                TransformRequestWorkflow.run,
                TransformRequestInput(
                    request_id=request_id,
                    did="mc23:some.dataset",
                    did_scheme="rucio",
                    dataset_id=42,
                    image="img",
                    generated_code_cm="cm",
                    transformer_language="python",
                    transformer_command="cmd",
                    result_destination="object-store",
                    result_format="parquet",
                    max_workers=2,
                    tuning=TransformRequestTuning(
                        batch_size=3, pool_reconcile_seconds=1
                    ),
                ),
                id=f"transform-{request_id}",
                task_queue=task_queue,
            )

    ours = [
        r
        for r in capture.records
        if r.name in ("temporalio.workflow", "temporalio.activity")
    ]
    lookup = [r for r in ours if (r.workflow_id or "").startswith("dataset-")]
    request = [r for r in ours if r not in lookup]

    assert request, "expected stub logs from the request's workflows"
    assert {r.request_id for r in request} == {request_id}
    # The shared lookup is keyed on the dataset, like the DID finders' logs.
    assert lookup
    assert {r.request_id for r in lookup} == {None}
    assert {r.dataset_id for r in lookup if r.getMessage().startswith("STUB")} == {42}
    messages = [r.getMessage() for r in request]
    assert any(m.startswith("STUB finalize_request") for m in messages)
    assert any(m.startswith("STUB transform_file") for m in messages)
    assert any(m.startswith("STUB launch_pilots") for m in messages)
