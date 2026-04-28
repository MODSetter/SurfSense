"""Tests for BusyMutexMiddleware: per-thread lock + cancel event behavior."""

from __future__ import annotations

import pytest

from app.agents.new_chat.errors import BusyError
from app.agents.new_chat.middleware.busy_mutex import (
    BusyMutexMiddleware,
    get_cancel_event,
    manager,
    request_cancel,
    reset_cancel,
)

pytestmark = pytest.mark.unit


class _Runtime:
    def __init__(self, thread_id: str | None) -> None:
        self.config = {"configurable": {"thread_id": thread_id}}


@pytest.mark.asyncio
async def test_first_acquire_succeeds_and_release_unblocks() -> None:
    mw = BusyMutexMiddleware()
    runtime = _Runtime("t1")
    await mw.abefore_agent({}, runtime)

    # Lock should now be held
    lock = manager.lock_for("t1")
    assert lock.locked()

    await mw.aafter_agent({}, runtime)
    assert not lock.locked()


@pytest.mark.asyncio
async def test_second_concurrent_acquire_raises_busy() -> None:
    mw_a = BusyMutexMiddleware()
    mw_b = BusyMutexMiddleware()
    runtime = _Runtime("t-conflict")
    await mw_a.abefore_agent({}, runtime)

    with pytest.raises(BusyError) as excinfo:
        await mw_b.abefore_agent({}, runtime)
    assert excinfo.value.request_id == "t-conflict"

    await mw_a.aafter_agent({}, runtime)
    # After release, mw_b can acquire
    await mw_b.abefore_agent({}, runtime)
    await mw_b.aafter_agent({}, runtime)


@pytest.mark.asyncio
async def test_cancel_event_lifecycle() -> None:
    mw = BusyMutexMiddleware()
    runtime = _Runtime("t-cancel")

    await mw.abefore_agent({}, runtime)
    event = get_cancel_event("t-cancel")
    assert not event.is_set()

    request_cancel("t-cancel")
    assert event.is_set()

    # End of turn should reset
    await mw.aafter_agent({}, runtime)
    assert not event.is_set()


@pytest.mark.asyncio
async def test_no_thread_id_raises_when_required() -> None:
    mw = BusyMutexMiddleware(require_thread_id=True)
    runtime = _Runtime(None)
    with pytest.raises(BusyError):
        await mw.abefore_agent({}, runtime)


@pytest.mark.asyncio
async def test_no_thread_id_skipped_when_not_required() -> None:
    mw = BusyMutexMiddleware(require_thread_id=False)
    runtime = _Runtime(None)
    await mw.abefore_agent({}, runtime)
    await mw.aafter_agent({}, runtime)


def test_reset_cancel_idempotent() -> None:
    # Should not raise even if event was never created
    reset_cancel("never-seen")
