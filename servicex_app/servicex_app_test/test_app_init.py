import json
import logging
import os
import queue
import sys
from logging.handlers import QueueListener

import pytest

import servicex_app
from servicex_app import (
    LogstashFormatter,
    StreamFormatter,
    VectorFormatter,
    _DirectQueueHandler,
    strtobool,
)


class TestStrToBool:
    @pytest.mark.parametrize(
        "value", ["y", "yes", "t", "true", "on", "1", "Y", "YES", "True", "ON"]
    )
    def test_truthy_values(self, value):
        assert strtobool(value) is True

    @pytest.mark.parametrize(
        "value", ["n", "no", "f", "false", "off", "0", "N", "NO", "False", "OFF"]
    )
    def test_falsy_values(self, value):
        assert strtobool(value) is False

    @pytest.mark.parametrize("value", ["", "maybe", "2", "yesplease"])
    def test_invalid_value_raises(self, value):
        with pytest.raises(ValueError, match="invalid truth value"):
            strtobool(value)


class TestAppInit:
    def test_read_from_config(self):
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        os.environ["ALLOWED_IMAGE_PREFIXES"] = '["sslhep/"]'
        app = servicex_app.create_app()
        assert app.config["FOO"] == "bar"
        assert app.config["SECRET_VALUE"] == "blah"
        assert not app.config["BOOL_VALUE"]

        os.environ["SECRET_VALUE"] = "shhh"
        os.environ["BOOL_VALUE"] = "true"
        app_from_env = servicex_app.create_app()
        assert app_from_env.config["SECRET_VALUE"] == "shhh"
        assert app_from_env.config["BOOL_VALUE"]

    def test_app_init_without_allowed_prefixes(self, monkeypatch):
        """Test that app creation fails when ALLOWED_IMAGE_PREFIXES is not set"""
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        monkeypatch.delenv("ALLOWED_IMAGE_PREFIXES", raising=False)
        with pytest.raises(ValueError, match="must be configured"):
            servicex_app.create_app()


class TestUserCli:
    @pytest.fixture
    def app(self):
        os.environ["APP_CONFIG_FILE"] = str(
            os.path.join(os.path.dirname(__file__), "test.config")
        )
        os.environ["ALLOWED_IMAGE_PREFIXES"] = '["sslhep/"]'
        return servicex_app.create_app()

    def test_approve_command_dispatches_to_approve_user(self, app, mocker):
        mock = mocker.patch("servicex_app.approve_user")
        result = app.test_cli_runner().invoke(args=["user", "approve", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com")

    def test_make_admin_command_dispatches_to_set_user_admin(self, app, mocker):
        mock = mocker.patch("servicex_app.set_user_admin")
        result = app.test_cli_runner().invoke(args=["user", "make-admin", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com", True)

    def test_revoke_admin_command_dispatches_to_set_user_admin(self, app, mocker):
        mock = mocker.patch("servicex_app.set_user_admin")
        result = app.test_cli_runner().invoke(args=["user", "revoke-admin", "x@y.com"])
        assert result.exit_code == 0
        mock.assert_called_once_with("x@y.com", False)


def _make_record(msg="hello %s", args=("world",), exc_info=None, **extra):
    record = logging.LogRecord(
        name="servicex_app",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )
    record.__dict__.update(extra)
    return record


def _exc_info():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        return sys.exc_info()


class TestStreamFormatter:
    def test_format_appends_extras(self):
        formatter = StreamFormatter("%(levelname)s %(message)s")
        assert (
            formatter.format(_make_record(request_id="req-1"))
            == "INFO hello world extra: {'request_id': 'req-1'}"
        )

    def test_format_without_extras(self):
        formatter = StreamFormatter("%(levelname)s %(message)s")
        # taskName was added to LogRecord in Python 3.12
        record = _make_record()
        record.__dict__.pop("taskName", None)
        assert formatter.format(record) == "INFO hello world"


class TestLogstashFormatter:
    def test_format(self):
        formatter = LogstashFormatter("logstash", None, None)
        message = json.loads(formatter.format(_make_record(request_id="req-1")))

        assert message["@version"] == "1"
        assert message["message"] == "hello world"
        assert message["type"] == "logstash"
        assert message["component"] == "servicex_app"
        assert message["level"] == "INFO"
        assert message["logger_name"] == "servicex_app"
        assert message["request_id"] == "req-1"
        assert "stack_trace" not in message

    def test_format_adds_traceback(self):
        formatter = LogstashFormatter("logstash", None, None)
        message = json.loads(formatter.format(_make_record(exc_info=_exc_info())))

        assert "RuntimeError: boom" in message["stack_trace"]


class TestVectorFormatter:
    def test_format_maps_record_to_columns(self):
        formatter = VectorFormatter("vector", None, None)
        record = _make_record(request_id="req-1", dataset_id=7, foo="bar")

        message = json.loads(formatter.format(record))

        assert message["level"] == "INFO"
        assert message["logger"] == "servicex_app"
        assert message["component"] == "servicex_app"
        assert message["instance"] == servicex_app.instance
        assert message["message"] == "hello world"
        assert message["timestamp"].endswith("Z")
        assert message["request_id"] == "req-1"
        assert message["dataset_id"] == 7
        assert message["extra"]["foo"] == "bar"
        assert "request_id" not in message["extra"]
        assert "dataset_id" not in message["extra"]
        assert "stack_trace" not in message["extra"]

    def test_format_defaults_ids_to_none(self):
        formatter = VectorFormatter("vector", None, None)
        message = json.loads(formatter.format(_make_record()))

        assert message["request_id"] is None
        assert message["dataset_id"] is None

    def test_format_returns_bytes(self):
        formatter = VectorFormatter("vector", None, None)
        assert isinstance(formatter.format(_make_record()), bytes)

    def test_format_adds_traceback_to_extra(self):
        formatter = VectorFormatter("vector", None, None)
        record = _make_record(exc_info=_exc_info())

        message = json.loads(formatter.format(record))

        assert "RuntimeError: boom" in message["extra"]["stack_trace"]
        assert message["extra"]["lineno"] == 42


class TestDirectQueueHandler:
    def test_prepare_returns_record_unmodified(self):
        handler = _DirectQueueHandler(queue.Queue())
        exc_info = _exc_info()
        record = _make_record(exc_info=exc_info)

        prepared = handler.prepare(record)

        assert prepared is record
        assert prepared.exc_info is exc_info
        assert prepared.msg == "hello %s"
        assert prepared.args == ("world",)

    def test_traceback_survives_queue_listener(self):
        """A record logged with exc_info reaches VectorFormatter on the listener
        thread with its traceback intact."""
        formatted = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                formatted.append(json.loads(self.format(record)))

        capture = CaptureHandler()
        capture.setFormatter(VectorFormatter("vector", None, None))

        log_queue = queue.Queue(-1)
        logger = logging.getLogger("test_vector_queue")
        logger.propagate = False
        queue_handler = _DirectQueueHandler(log_queue)
        logger.addHandler(queue_handler)
        listener = QueueListener(log_queue, capture, respect_handler_level=True)
        listener.start()
        try:
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                logger.exception("failed", extra={"request_id": "req-1"})
        finally:
            listener.stop()
            logger.removeHandler(queue_handler)

        assert len(formatted) == 1
        assert formatted[0]["message"] == "failed"
        assert formatted[0]["level"] == "ERROR"
        assert formatted[0]["request_id"] == "req-1"
        assert "RuntimeError: boom" in formatted[0]["extra"]["stack_trace"]


class TestLoggingSetup:
    @pytest.fixture
    def app_env(self, monkeypatch):
        monkeypatch.setenv(
            "APP_CONFIG_FILE",
            str(os.path.join(os.path.dirname(__file__), "test.config")),
        )
        monkeypatch.setenv("ALLOWED_IMAGE_PREFIXES", '["sslhep/"]')
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        monkeypatch.delenv("LOGSTASH_HOST", raising=False)
        monkeypatch.delenv("LOGSTASH_PORT", raising=False)
        monkeypatch.delenv("VECTOR_HOST", raising=False)
        monkeypatch.delenv("VECTOR_PORT", raising=False)

        logger = logging.getLogger("servicex_app")
        original_handlers = list(logger.handlers)
        yield monkeypatch
        for h in list(logger.handlers):
            if h not in original_handlers:
                logger.removeHandler(h)

    def test_vector_handler_not_added_without_env(self, app_env, mocker):
        mock_listener = mocker.patch("servicex_app.QueueListener")
        mock_tcp = mocker.patch("servicex_app.logstash.TCPLogstashHandler")

        servicex_app.create_app()

        mock_listener.assert_not_called()
        mock_tcp.assert_not_called()

    def test_vector_handler_wired_through_queue(self, app_env, mocker):
        app_env.setenv("VECTOR_HOST", "vector.svc")
        app_env.setenv("VECTOR_PORT", "6000")
        mock_listener = mocker.patch("servicex_app.QueueListener")
        mock_tcp = mocker.patch("servicex_app.logstash.TCPLogstashHandler")

        app = servicex_app.create_app()

        mock_tcp.assert_called_once_with("vector.svc", 6000, version=1)
        vector_handler = mock_tcp.return_value
        formatter = vector_handler.setFormatter.call_args.args[0]
        assert isinstance(formatter, VectorFormatter)
        vector_handler.setLevel.assert_called_once_with("INFO")

        mock_listener.assert_called_once()
        log_queue, handler = mock_listener.call_args.args
        assert handler is vector_handler
        assert mock_listener.call_args.kwargs == {"respect_handler_level": True}
        mock_listener.return_value.start.assert_called_once()

        queue_handlers = [
            h
            for h in app.logger.handlers
            if isinstance(h, _DirectQueueHandler) and h.queue is log_queue
        ]
        assert len(queue_handlers) == 1
        assert queue_handlers[0].level == logging.INFO

    def test_logstash_handler_added_with_env(self, app_env, mocker):
        app_env.setenv("LOGSTASH_HOST", "logstash.svc")
        app_env.setenv("LOGSTASH_PORT", "5959")
        mock_tcp = mocker.patch("servicex_app.logstash.TCPLogstashHandler")
        mock_tcp.return_value.level = logging.INFO

        app = servicex_app.create_app()

        mock_tcp.assert_called_once_with("logstash.svc", "5959", version=1)
        logstash_handler = mock_tcp.return_value
        formatter = logstash_handler.setFormatter.call_args.args[0]
        assert isinstance(formatter, LogstashFormatter)
        assert logstash_handler in app.logger.handlers
