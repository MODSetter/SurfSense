"""Lock the ``with_retries`` policy: budget, recovery, exhaustion, timeout, backoff.

Tests with ``backoff="none"`` to keep wall-clock time zero. Backoff sleep
values themselves are observed by monkeypatching ``asyncio.sleep`` so we
don't introduce flakiness via real timing.
"""

from __future__ import annotations

import pytest

from app.automations.runtime.retries import with_retries

pytestmark = pytest.mark.unit


async def test_with_retries_returns_result_and_attempts_one_on_first_success() -> None:
    """A coroutine that succeeds on the first call returns its result
    paired with ``attempts=1`` — no retry consumed."""
    calls = 0

    async def succeed() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result, attempts = await with_retries(
        succeed, max_retries=2, backoff="none", timeout=None
    )

    assert result == "ok"
    assert attempts == 1
    assert calls == 1


async def test_with_retries_returns_attempt_count_when_succeeding_after_failures() -> None:
    """A coroutine that fails twice then succeeds returns ``attempts=3``
    (the actual attempt that produced the result). Locks the contract
    that the caller can distinguish first-try success from a recovery."""
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("transient")
        return "ok"

    result, attempts = await with_retries(
        flaky, max_retries=5, backoff="none", timeout=None
    )

    assert result == "ok"
    assert attempts == 3
    assert calls == 3


async def test_with_retries_reraises_after_exhausting_the_budget() -> None:
    """When the coroutine raises on every attempt within
    ``1 + max_retries`` tries, the last exception propagates and the
    handler is called exactly ``1 + max_retries`` times."""
    calls = 0

    async def always_fails() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError(f"boom-{calls}")

    with pytest.raises(RuntimeError, match="boom-3"):
        await with_retries(always_fails, max_retries=2, backoff="none", timeout=None)

    assert calls == 3  # 1 initial + 2 retries
