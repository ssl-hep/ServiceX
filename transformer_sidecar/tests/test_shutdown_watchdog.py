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
"""
Unit tests for ShutdownWatchdog. Because the class owns its own state, no
module-level cleanup is required between tests.
"""

import signal

import pytest
from amqp.exceptions import NotFound

from transformer_sidecar.shutdown_watchdog import ShutdownWatchdog


def _response(mocker, status_code=200, payload=None):
    response = mocker.MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    return response


def _celery_app(mocker, message_count=0, error=None):
    """A Celery app whose broker reports `message_count` ready messages."""
    app = mocker.MagicMock()
    channel = app.connection_for_read.return_value.__enter__.return_value
    channel = channel.default_channel
    if error is not None:
        channel.queue_declare.side_effect = error
    else:
        channel.queue_declare.return_value = (
            "transformer-test-request",
            message_count,
            1,
        )
    return app


def _make(mocker, **overrides):
    """Build a watchdog with sensible defaults; overrides supersede."""
    kwargs = dict(
        status_url="http://svc/status",
        request_id="test-request",
        place={"host": "test-host", "site": "test-site", "pod": "test-pod"},
        celery_app=_celery_app(mocker),
        poll_interval=1.0,
    )
    kwargs.update(overrides)
    return ShutdownWatchdog(**kwargs)


def _queue_declare(wd):
    conn = wd.celery_app.connection_for_read.return_value.__enter__.return_value
    return conn.default_channel.queue_declare


class TestShouldShutdown:
    """_should_shutdown() gates the actual worker shutdown."""

    def test_true_when_lookup_complete_and_no_files_remaining(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(
                mocker,
                payload={"lookup_complete": True, "files_remaining": 0},
            ),
        )
        assert wd._should_shutdown() is True

    def test_false_when_files_still_remaining(self, mocker):
        # The queue is empty, but another worker still has a file in flight
        # that may yet be retried.
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(
                mocker,
                payload={"lookup_complete": True, "files_remaining": 12},
            ),
        )
        assert wd._should_shutdown() is False

    def test_false_when_file_count_not_known_yet(self, mocker):
        # files_remaining is None until the server has a count to report.
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(
                mocker,
                payload={"lookup_complete": True, "files_remaining": None},
            ),
        )
        assert wd._should_shutdown() is False

    def test_false_when_lookup_pending(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(
                mocker,
                payload={"lookup_complete": False, "files_remaining": 0},
            ),
        )
        assert wd._should_shutdown() is False

    def test_true_when_transform_reached_terminal_state(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(
                mocker,
                payload={"lookup_complete": False, "transform_complete": True},
            ),
        )
        assert wd._should_shutdown() is True

    def test_false_on_transient_error(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            side_effect=RuntimeError("connection refused"),
        )
        assert wd._should_shutdown() is False

    def test_false_on_5xx(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(mocker, status_code=502),
        )
        assert wd._should_shutdown() is False


class TestQueueCheckComesFirst:
    def test_work_on_queue_skips_server_poll(self, mocker):
        wd = _make(mocker, celery_app=_celery_app(mocker, message_count=3))
        get = mocker.patch("transformer_sidecar.shutdown_watchdog.requests.get")

        assert wd._should_shutdown() is False
        get.assert_not_called()

    def test_empty_queue_goes_on_to_poll_server(self, mocker):
        wd = _make(mocker)
        get = mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(mocker, payload={"transform_complete": True}),
        )

        assert wd._should_shutdown() is True
        get.assert_called_once_with("http://svc/status", timeout=10)


class TestQueueIsEmpty:
    def test_declares_request_queue_passively(self, mocker):
        # A passive declare only inspects the queue; it must never create
        # one or clash with the arguments the queue was declared with.
        wd = _make(mocker)
        assert wd._queue_is_empty() is True
        _queue_declare(wd).assert_called_once_with(
            queue="transformer-test-request", passive=True
        )

    def test_false_when_messages_ready(self, mocker):
        wd = _make(mocker, celery_app=_celery_app(mocker, message_count=1))
        assert wd._queue_is_empty() is False

    def test_missing_queue_counts_as_empty(self, mocker):
        # An auto-delete queue disappears once its consumers are cancelled;
        # there is nothing left to wait for.
        error = NotFound("no queue 'transformer-test-request'")
        wd = _make(mocker, celery_app=_celery_app(mocker, error=error))
        assert wd._queue_is_empty() is True

    def test_broker_error_is_treated_as_work_remaining(self, mocker):
        error = ConnectionError("broker unreachable")
        wd = _make(mocker, celery_app=_celery_app(mocker, error=error))
        assert wd._queue_is_empty() is False


class TestRequestShutdown:
    """Shutdown must stay local to this worker, never fan out on the broker."""

    def test_signals_only_this_process(self, mocker):
        wd = _make(mocker)
        kill = mocker.patch("transformer_sidecar.shutdown_watchdog.os.kill")
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.os.getpid", return_value=4242
        )

        wd._request_shutdown()

        kill.assert_called_once_with(4242, signal.SIGTERM)

    def test_signal_failure_is_swallowed(self, mocker):
        wd = _make(mocker)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.os.kill",
            side_effect=OSError("no such process"),
        )
        # Should not raise.
        wd._request_shutdown()


class TestRun:
    """The _run loop keeps polling until _should_shutdown returns True."""

    def test_loop_shuts_down_when_ready(self, mocker):
        wd = _make(mocker, poll_interval=0.01)
        request_shutdown = mocker.patch.object(wd, "_request_shutdown")
        # First two polls: not ready. Third: ready.
        mocker.patch.object(wd, "_should_shutdown", side_effect=[False, False, True])
        wd._run()
        request_shutdown.assert_called_once()

    def test_loop_exits_cleanly_on_stop(self, mocker):
        wd = _make(mocker, poll_interval=0.01)
        request_shutdown = mocker.patch.object(wd, "_request_shutdown")
        # Set stop before entering the loop; wait() returns True immediately.
        wd._stop_event.set()
        mocker.patch.object(wd, "_should_shutdown", return_value=True)
        wd._run()
        request_shutdown.assert_not_called()


class TestLifecycle:
    def test_start_twice_raises(self, mocker):
        wd = _make(mocker)
        # Stub the thread so nothing actually runs.
        mocker.patch("transformer_sidecar.shutdown_watchdog.threading.Thread")
        wd.start()

        with pytest.raises(RuntimeError):
            wd.start()

    def test_stop_halts_the_loop(self, mocker):
        wd = _make(mocker)
        wd.stop()
        assert wd._stop_event.is_set()


class TestPoll:
    def test_unparseable_body_is_treated_as_no_answer(self, mocker):
        # A 200 that isn't JSON tells us nothing about the request, so the
        # watchdog must not read it as permission to shut down.
        response = _response(mocker)
        response.json.side_effect = ValueError("not json")
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=response,
        )
        wd = _make(mocker)

        assert wd._poll() is None
        assert wd._should_shutdown() is False
