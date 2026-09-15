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
import logging
import os
import signal
import threading
import time
from typing import Optional

import requests
from celery.signals import task_postrun, task_prerun

logger = logging.getLogger(__name__)


class ShutdownWatchdog:
    """
    Poll the ServiceX status endpoint; once the server reports that this
    request has no work left and this worker has been idle for
    `idle_shutdown_seconds`, ask the worker to shut down warmly so the pod
    exits and its Job can complete naturally.

    All state lives on the instance: constructing a new watchdog for tests
    is safe and does not touch other instances.
    """

    def __init__(
        self,
        status_url: str,
        request_id: str,
        place: dict,
        poll_interval: float = 30.0,
        idle_shutdown_seconds: float = 60.0,
    ):
        self.status_url = status_url
        self.request_id = request_id
        self.place = place
        self.poll_interval = poll_interval
        self.idle_shutdown_seconds = idle_shutdown_seconds

        self._lock = threading.Lock()
        self._last_activity = time.time()
        self._connections: list = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def register_activity_signals(self) -> None:
        """Bind to Celery task lifecycle signals so activity is tracked."""
        # weak=False keeps Celery from garbage-collecting bound methods.
        task_prerun.connect(self._on_task_event, weak=False)
        task_postrun.connect(self._on_task_event, weak=False)
        self._connections = [
            (task_prerun, self._on_task_event),
            (task_postrun, self._on_task_event),
        ]

    def disconnect_signals(self) -> None:
        for sig, handler in self._connections:
            sig.disconnect(handler)
        self._connections = []

    def _on_task_event(self, *args, **kwargs) -> None:
        with self._lock:
            self._last_activity = time.time()

    @property
    def last_activity(self) -> float:
        with self._lock:
            return self._last_activity

    def idle_seconds(self) -> float:
        return time.time() - self.last_activity

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("ShutdownWatchdog already started")
        self._thread = threading.Thread(
            target=self._run, name="shutdown-watchdog", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Ask the watchdog thread to exit and unregister its signal handlers."""
        self._stop_event.set()
        self.disconnect_signals()

    def _run(self) -> None:
        # wait() returns True if the stop event fires, False on timeout.
        while not self._stop_event.wait(self.poll_interval):
            if not self._should_shutdown():
                continue

            logger.info(
                "No work left for this request and worker idle for "
                f"{self.idle_seconds():.1f}s; requesting shutdown.",
                extra={"request_id": self.request_id, "place": self.place},
            )
            self._request_shutdown()
            return

    def _request_shutdown(self) -> None:
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception as exc:
            logger.warning(
                f"Shutdown request failed: {exc}",
                extra={"request_id": self.request_id, "place": self.place},
            )

    def _should_shutdown(self) -> bool:
        """
        A worker may only exit once the server says no more work is coming for
        this request: the DID finder has finished (`lookup_complete`) *and*
        every file it found has been accounted for (`files_remaining` is 0).
        """
        if self.idle_seconds() < self.idle_shutdown_seconds:
            return False
        payload = self._poll()
        if payload is None:
            return False
        if payload.get("transform_complete"):
            return True
        if not payload.get("lookup_complete"):
            return False
        files_remaining = payload.get("files_remaining")
        return files_remaining is not None and files_remaining <= 0

    def _poll(self) -> Optional[dict]:
        try:
            response = requests.get(self.status_url, timeout=10)
        except Exception as exc:
            logger.debug(
                f"Shutdown watchdog: status poll failed: {exc}",
                extra={"request_id": self.request_id, "place": self.place},
            )
            return None

        if response.status_code != 200:
            logger.debug(
                f"Shutdown watchdog: status returned {response.status_code}",
                extra={"request_id": self.request_id, "place": self.place},
            )
            return None

        try:
            return response.json()
        except Exception:
            return None
