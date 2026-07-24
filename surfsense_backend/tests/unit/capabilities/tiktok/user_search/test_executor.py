"""``tiktok.user_search`` executor: verb input → search args → typed profile items.

Boundary mocked: the proprietary search actor (injected fake). NOT mocked: the
verb's own payload→args forwarding and the dict→TikTokProfileItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.tiktok.user_search.executor import build_user_search_executor
from app.capabilities.tiktok.user_search.schemas import (
    UserSearchInput,
    UserSearchOutput,
)

pytestmark = pytest.mark.unit


class _FakeSearch:
    """Records the queries + kwargs it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[list[str], int, int | None]] = []

    async def __call__(
        self, queries: list[str], *, per_query: int, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((queries, per_query, limit))
        return self._items


async def test_forwards_queries_and_limits_and_wraps_items():
    search = _FakeSearch([{"id": "1", "name": "nasa"}])
    execute = build_user_search_executor(search_fn=search)

    out = await execute(
        UserSearchInput(queries=["nasa"], results_per_query=7, max_items=25)
    )

    assert isinstance(out, UserSearchOutput)
    assert len(out.items) == 1
    assert out.items[0].name == "nasa"

    (queries, per_query, limit) = search.calls[0]
    assert queries == ["nasa"]
    assert per_query == 7
    assert limit == 25
