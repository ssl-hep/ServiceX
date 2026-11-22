import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from temporalio.exceptions import ApplicationError, CancelledError

from servicex_orchestrator.workflows import common


def _external_handle(monkeypatch, error=None, cancellation_reason=None):
    handle = MagicMock()
    handle.signal = AsyncMock(side_effect=error)
    monkeypatch.setattr(
        common.workflow, "get_external_workflow_handle", lambda _id: handle
    )
    monkeypatch.setattr(common.workflow, "logger", MagicMock())
    monkeypatch.setattr(
        common.workflow, "cancellation_reason", lambda: cancellation_reason
    )


async def test_signal_to_gone_workflow_returns_false(monkeypatch):
    _external_handle(monkeypatch, ApplicationError("not found"))
    assert await common.signal_workflow("pool-1", "backlog", 1, 1) is False


async def test_cancellation_while_signalling_is_not_swallowed(monkeypatch):
    """Regression: a workflow canceled with a signal pending ran on to completion."""
    _external_handle(monkeypatch, CancelledError("canceled"))
    with pytest.raises(asyncio.CancelledError):
        await common.signal_workflow("pool-1", "backlog", 1, 1)


async def test_delivered_signal_returns_true(monkeypatch):
    _external_handle(monkeypatch)
    assert await common.signal_workflow("pool-1", "backlog", 1, 1) is True


async def test_cancel_during_delivered_signal_is_not_lost(monkeypatch):
    """Regression: the cancel lands while a signal already sent is pending. The SDK
    returns the signal's success and drops the cancellation; we must re-raise it."""
    _external_handle(monkeypatch, cancellation_reason="")
    with pytest.raises(asyncio.CancelledError):
        await common.signal_workflow("pool-1", "backlog", 1, 1)
