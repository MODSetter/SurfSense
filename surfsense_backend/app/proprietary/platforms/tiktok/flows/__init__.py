"""Per-target scrape flows: resolved target -> normalized items."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

FetchFn = Callable[[str], Awaitable[str | None]]
FlowResult = AsyncIterator[dict]
