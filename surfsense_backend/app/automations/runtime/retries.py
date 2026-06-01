"""Retry policy enforcement for action handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


async def with_retries[T](
    coro_factory: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    backoff: str,
    timeout: int | None,
) -> tuple[T, int]:
    """Call ``coro_factory`` up to ``1 + max_retries`` times. Return ``(result, attempts)``."""
    total = 1 + max(0, max_retries)
    for attempt in range(1, total + 1):
        try:
            coro = coro_factory()
            if timeout is not None and timeout > 0:
                return await asyncio.wait_for(coro, timeout=timeout), attempt
            return await coro, attempt
        except Exception:
            if attempt >= total:
                raise
            await asyncio.sleep(_backoff_seconds(backoff, attempt))
    raise RuntimeError("with_retries exhausted without raising or returning")


def _backoff_seconds(strategy: str, attempt: int) -> float:
    if strategy == "exponential":
        return float(2 ** (attempt - 1))
    if strategy == "linear":
        return float(attempt)
    return 0.0
