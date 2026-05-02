"""Tests for BusyMutexMiddleware: per-thread lock + cancel event behavior."""

from __future__ import annotations

import pytest

from app.agents.new_chat.errors import BusyError
from app.agents.new_chat.middleware.busy_mutex import (
    BusyMutexMiddleware,
    end_turn,
    get_cancel_event,
    is_cancel_requested,
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


def test_request_cancel_creates_event_for_unseen_thread() -> None:
    thread_id = "never-seen-cancel"
    reset_cancel(thread_id)

    assert request_cancel(thread_id) is True
    assert get_cancel_event(thread_id).is_set()
    assert is_cancel_requested(thread_id) is True


@pytest.mark.asyncio
async def test_end_turn_force_clears_lock_and_cancel_state() -> None:
    thread_id = "forced-end-turn"
    mw = BusyMutexMiddleware()
    runtime = _Runtime(thread_id)

    await mw.abefore_agent({}, runtime)
    assert manager.lock_for(thread_id).locked()

    request_cancel(thread_id)
    assert is_cancel_requested(thread_id) is True

    end_turn(thread_id)

    assert not manager.lock_for(thread_id).locked()
    assert not get_cancel_event(thread_id).is_set()
    assert is_cancel_requested(thread_id) is False


@pytest.mark.asyncio
async def test_busy_mutex_stale_aafter_does_not_release_new_attempt_lock() -> None:
    """A stale aafter call from attempt A must not unlock attempt B.

    Repro flow:
    1) attempt A acquires thread lock
    2) forced end_turn clears A so retry can proceed
    3) attempt B acquires same thread lock
    4) stale attempt-A aafter runs late

    Expected: B lock remains held.
    """
    thread_id = "stale-aafter-lock"
    runtime = _Runtime(thread_id)
    attempt_a = BusyMutexMiddleware()
    attempt_b = BusyMutexMiddleware()

    await attempt_a.abefore_agent({}, runtime)
    lock = manager.lock_for(thread_id)
    assert lock.locked()

    end_turn(thread_id)
    assert not lock.locked()

    await attempt_b.abefore_agent({}, runtime)
    assert lock.locked()

    # Stale cleanup from attempt A must not release attempt B's lock.
    await attempt_a.aafter_agent({}, runtime)
    assert lock.locked()

    await attempt_b.aafter_agent({}, runtime)
