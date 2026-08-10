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

from transformer_sidecar.shutdown_watchdog import ShutdownWatchdog


def _response(mocker, status_code=200, payload=None):
    response = mocker.MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    return response


def _make(mocker, **overrides):
    """Build a watchdog with sensible defaults; overrides supersede."""
    kwargs = dict(
        app=mocker.MagicMock(),
        status_url="http://svc/status",
        poll_interval=1.0,
        idle_shutdown_seconds=60.0,
    )
    kwargs.update(overrides)
    return ShutdownWatchdog(**kwargs)


class TestShouldShutdown:
    """_should_shutdown() gates the actual celery shutdown call."""

    def test_true_when_lookup_complete_and_idle(self, mocker):
        wd = _make(mocker)
        # Force worker to look "idle for a long time".
        wd._last_activity = 0.0
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(mocker, payload={"lookup_complete": True}),
        )
        assert wd._should_shutdown() is True

    def test_false_when_lookup_pending(self, mocker):
        wd = _make(mocker)
        wd._last_activity = 0.0
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(mocker, payload={"lookup_complete": False}),
        )
        assert wd._should_shutdown() is False

    def test_false_when_worker_still_busy(self, mocker):
        # last_activity = "now" => idle for ~0 seconds
        wd = _make(mocker, idle_shutdown_seconds=60.0)
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.requests.get",
            return_value=_response(mocker, payload={"lookup_complete": True}),
        )
        assert wd._should_shutdown() is False

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


class TestActivityTracking:
    """last_activity is refreshed whenever the signal handler fires."""

    def test_task_event_updates_last_activity(self, mocker):
        wd = _make(mocker)
        wd._last_activity = 0.0
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.time.time",
            return_value=1234.5,
        )
        wd._on_task_event()
        assert wd._last_activity == 1234.5

    def test_idle_seconds_matches_wallclock_diff(self, mocker):
        wd = _make(mocker)
        wd._last_activity = 100.0
        mocker.patch(
            "transformer_sidecar.shutdown_watchdog.time.time",
            return_value=160.0,
        )
        assert wd.idle_seconds() == 60.0


class TestRun:
    """The _run loop keeps polling until _should_shutdown returns True."""

    def test_loop_broadcasts_shutdown_when_ready(self, mocker):
        wd = _make(mocker, poll_interval=0.01)
        # First two polls: not ready. Third: ready.
        mocker.patch.object(wd, "_should_shutdown", side_effect=[False, False, True])
        wd._run()
        wd.app.control.shutdown.assert_called_once()

    def test_loop_exits_cleanly_on_stop(self, mocker):
        wd = _make(mocker, poll_interval=0.01)
        # Set stop before entering the loop; wait() returns True immediately.
        wd._stop_event.set()
        mocker.patch.object(wd, "_should_shutdown", return_value=True)
        wd._run()
        wd.app.control.shutdown.assert_not_called()

    def test_shutdown_broadcast_failure_is_swallowed(self, mocker):
        wd = _make(mocker, poll_interval=0.01)
        wd.app.control.shutdown.side_effect = RuntimeError("broker down")
        mocker.patch.object(wd, "_should_shutdown", return_value=True)
        # Should not raise.
        wd._run()
        wd.app.control.shutdown.assert_called_once()


class TestSignalRegistration:
    """register_activity_signals() plumbs celery signals to _on_task_event."""

    def test_registers_and_disconnects(self, mocker):
        wd = _make(mocker)
        prerun = mocker.patch("transformer_sidecar.shutdown_watchdog.task_prerun")
        postrun = mocker.patch("transformer_sidecar.shutdown_watchdog.task_postrun")

        wd.register_activity_signals()
        prerun.connect.assert_called_once_with(wd._on_task_event, weak=False)
        postrun.connect.assert_called_once_with(wd._on_task_event, weak=False)

        wd.disconnect_signals()
        prerun.disconnect.assert_called_once_with(wd._on_task_event)
        postrun.disconnect.assert_called_once_with(wd._on_task_event)


class TestLifecycle:
    def test_start_twice_raises(self, mocker):
        wd = _make(mocker)
        # Stub the thread so nothing actually runs.
        mocker.patch("transformer_sidecar.shutdown_watchdog.threading.Thread")
        wd.start()
        import pytest

        with pytest.raises(RuntimeError):
            wd.start()
