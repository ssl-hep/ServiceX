import json
import logging

import pytest

from transformer_sidecar import transformer_logging
from transformer_sidecar.transformer_logging import initialize_logging
from transformer_sidecar.transformer_logging.vector_formatter import VectorFormatter

# Columns of the Postgres log_messages table that the vector sidecar inserts into.
LOG_MESSAGE_COLUMNS = {
    "timestamp",
    "level",
    "logger",
    "instance",
    "component",
    "message",
    "request_id",
    "extra",
}


def _record(**extra):
    record = logging.LogRecord(
        name="transformer_sidecar.transformer",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Transformed %s files",
        args=(3,),
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def _format(record):
    formatted = VectorFormatter("vector", None, None).format(record)
    return json.loads(formatted.decode("utf-8"))


def test_vector_formatter_emits_log_message_columns():
    event = _format(_record(request_id="abc-123"))

    assert set(event) == LOG_MESSAGE_COLUMNS
    assert event["component"] == "transformer_sidecar"
    assert event["level"] == "INFO"
    assert event["message"] == "Transformed 3 files"


def test_vector_formatter_hoists_request_id_out_of_extra():
    """request_id is its own column, so it must not stay buried in the blob."""
    event = _format(_record(request_id="abc-123", file_id=7))

    assert event["request_id"] == "abc-123"
    assert "request_id" not in event["extra"]
    assert event["extra"]["file_id"] == 7


def test_vector_formatter_tolerates_missing_request_id():
    assert _format(_record())["request_id"] is None


@pytest.fixture
def no_vector_listener():
    """Leave the module-level listener the way we found it."""
    yield
    if transformer_logging._vector_listener is not None:
        transformer_logging._vector_listener.stop()
    transformer_logging._vector_listener = None
    transformer_logging._vector_queue = None


def test_initialize_logging_without_vector_env(monkeypatch, no_vector_listener):
    monkeypatch.delenv("VECTOR_HOST", raising=False)
    monkeypatch.delenv("VECTOR_PORT", raising=False)

    log = initialize_logging(logging.getLogger("test-no-vector"))

    assert transformer_logging._vector_listener is None
    assert not [h for h in log.handlers if isinstance(h, logging.handlers.QueueHandler)]


def _queue_handlers(log):
    return [h for h in log.handlers if isinstance(h, logging.handlers.QueueHandler)]


def test_initialize_logging_is_idempotent(monkeypatch, mocker, no_vector_listener):
    """
    initialize_logging runs twice on the same logger. The second run must not
    orphan the first run's listener, nor double-attach to the queue.
    """
    monkeypatch.setenv("VECTOR_HOST", "127.0.0.1")
    monkeypatch.setenv("VECTOR_PORT", "9000")
    # Don't open a real socket to a vector that isn't there.
    mocker.patch("logstash.TCPLogstashHandler.emit")

    log = logging.getLogger("test-idempotent")
    log.handlers.clear()

    initialize_logging(log)
    listener = transformer_logging._vector_listener
    assert listener is not None

    initialize_logging(log)

    assert transformer_logging._vector_listener is listener
    assert listener._thread.is_alive()
    assert len(_queue_handlers(log)) == 1


def test_initialize_logging_shares_one_listener_across_loggers(
    monkeypatch, mocker, no_vector_listener
):
    """
    The real call sites use two different loggers: the root logger at import,
    then Celery's from after_setup_logger. Both must feed the same live queue --
    a per-call listener would leave the first logger writing into a dead one.
    """
    monkeypatch.setenv("VECTOR_HOST", "127.0.0.1")
    monkeypatch.setenv("VECTOR_PORT", "9000")
    mocker.patch("logstash.TCPLogstashHandler.emit")

    first_log = logging.getLogger("test-first")
    second_log = logging.getLogger("test-second")
    first_log.handlers.clear()
    second_log.handlers.clear()

    initialize_logging(first_log)
    listener = transformer_logging._vector_listener

    initialize_logging(second_log)

    assert transformer_logging._vector_listener is listener
    assert listener._thread.is_alive()
    for log in (first_log, second_log):
        handlers = _queue_handlers(log)
        assert len(handlers) == 1
        assert handlers[0].queue is transformer_logging._vector_queue


def test_request_id_filter_stamps_records_that_lack_one(monkeypatch):
    """The celery.* loggers never pass extra={"request_id": ...}."""
    monkeypatch.setattr(transformer_logging, "request_id", "abc-123")
    record = _record()

    assert transformer_logging.RequestIdFilter().filter(record) is True
    assert _format(record)["request_id"] == "abc-123"


def test_request_id_filter_leaves_an_explicit_request_id_alone(monkeypatch):
    monkeypatch.setattr(transformer_logging, "request_id", "pod-wide")
    record = _record(request_id="from-call-site")

    transformer_logging.RequestIdFilter().filter(record)

    assert _format(record)["request_id"] == "from-call-site"


def test_request_id_filter_is_a_noop_before_init(monkeypatch):
    """Nothing to stamp until init() parses the args - leave the column null."""
    monkeypatch.setattr(transformer_logging, "request_id", None)
    record = _record()

    assert transformer_logging.RequestIdFilter().filter(record) is True
    assert _format(record)["request_id"] is None


def test_set_request_id_reaches_a_filter_built_earlier(monkeypatch):
    """
    The handlers are built at import, before --request-id has been parsed. The
    filter has to read the id when it runs, not capture it at construction.
    """
    monkeypatch.setattr(transformer_logging, "request_id", None)
    request_filter = transformer_logging.RequestIdFilter()

    transformer_logging.set_request_id("abc-123")

    record = _record()
    request_filter.filter(record)
    assert _format(record)["request_id"] == "abc-123"


def test_vector_queue_handler_carries_the_request_id_filter(
    monkeypatch, mocker, no_vector_listener
):
    monkeypatch.setenv("VECTOR_HOST", "127.0.0.1")
    monkeypatch.setenv("VECTOR_PORT", "9000")
    mocker.patch("logstash.TCPLogstashHandler.emit")

    log = logging.getLogger("test-request-id-filter")
    log.handlers.clear()

    initialize_logging(log)

    handler = _queue_handlers(log)[0]
    assert any(
        isinstance(f, transformer_logging.RequestIdFilter) for f in handler.filters
    )
