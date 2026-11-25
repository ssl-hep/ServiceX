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
import asyncio
import threading
from typing import Any, Coroutine, Optional

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError, RPCStatusCode

from servicex_app.models import TransformRequest

TRANSFORM_REQUEST_WORKFLOW = "TransformRequestWorkflow"


def transform_workflow_id(request_id: str) -> str:
    return f"transform-{request_id}"


class TemporalAdaptor:
    """Starts and controls the orchestrator's workflows from the (sync) Flask app.

    The temporalio client is asyncio-only, so the adaptor runs its own event loop on
    a daemon thread and hands coroutines to it. Both the loop and the connection are
    created on first use, never at construction. That keeps app start-up and tests
    free of network calls, and gunicorn workers (forked without --preload) each get
    their own connection.

    The workflow is started by name with a plain dict, so the app doesn't import the
    orchestrator package. The dict's keys must match the orchestrator's
    `servicex_orchestrator.models.TransformRequestInput`.
    """

    def __init__(
        self,
        address: str,
        namespace: str,
        task_queue: str,
        timeout_seconds: float = 30.0,
    ):
        self.address = address
        self.namespace = namespace
        self.task_queue = task_queue
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[Client] = None

    def start_transform_request(
        self, request_rec: TransformRequest, did_scheme: str, max_workers: int
    ) -> str:
        """Start TransformRequestWorkflow for this request; return its run id.

        Safe to call twice: a second start for the same request id attaches to the
        running workflow instead of starting another.
        """
        workflow_input = self.transform_request_input(
            request_rec, did_scheme, max_workers
        )
        return self._run(self._start(workflow_input))

    def cancel_transform_request(self, request_id: str) -> bool:
        """Ask TransformRequestWorkflow for this request to cancel.

        Returns True if a cancel was requested, False if there is no open workflow
        (never started, or already closed). The workflow cleans up on its own
        (cancels its batches and pool, deletes the pilots, finalizes the row), so
        this returns before that is done. Other errors propagate.
        """
        return self._run(self._cancel(request_id))

    @staticmethod
    def transform_request_input(
        request_rec: TransformRequest, did_scheme: str, max_workers: int
    ) -> dict:
        return {
            "request_id": request_rec.request_id,
            "did": request_rec.did,
            "did_scheme": did_scheme,
            "dataset_id": request_rec.did_id,
            "image": request_rec.image,
            "generated_code_cm": request_rec.generated_code_cm,
            "transformer_language": request_rec.transformer_language,
            "transformer_command": request_rec.transformer_command,
            "result_destination": request_rec.result_destination,
            "result_format": request_rec.result_format,
            "max_workers": max_workers,
        }

    async def _start(self, workflow_input: dict) -> str:
        client = await self._get_client()
        handle = await client.start_workflow(
            TRANSFORM_REQUEST_WORKFLOW,
            workflow_input,
            id=transform_workflow_id(workflow_input["request_id"]),
            task_queue=self.task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
        return handle.result_run_id

    async def _cancel(self, request_id: str) -> bool:
        client = await self._get_client()
        # No run id: the workflow continues-as-new, so target whichever run is
        # current.
        handle = client.get_workflow_handle(transform_workflow_id(request_id))
        try:
            await handle.cancel()
        except RPCError as err:
            if err.status == RPCStatusCode.NOT_FOUND:
                return False
            raise
        return True

    async def _get_client(self) -> Client:
        # Only ever runs on the adaptor's own loop thread, so no lock is needed.
        if self._client is None:
            self._client = await Client.connect(self.address, namespace=self.namespace)
        return self._client

    def _run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._get_loop())
        return future.result(timeout=self.timeout_seconds)

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(
                    target=loop.run_forever, name="temporal-adaptor", daemon=True
                ).start()
                self._loop = loop
            return self._loop
