"""``tiktok.trending`` executor: verb input → scraper count → typed video items.

Boundary mocked: the proprietary trending actor (injected fake). NOT mocked: the
verb's own count forwarding and the dict→TikTokVideoItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.tiktok.trending.executor import build_trending_executor
from app.capabilities.tiktok.trending.schemas import TrendingInput, TrendingOutput

pytestmark = pytest.mark.unit


class _FakeTrending:
    """Records the count it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[int] = []

    async def __call__(self, *, count: int) -> list[dict]:
        self.calls.append(count)
        return self._items


async def test_forwards_count_and_wraps_items():
    trending = _FakeTrending([{"id": "1", "text": "viral"}])
    execute = build_trending_executor(trending_fn=trending)

    out = await execute(TrendingInput(max_items=30))

    assert isinstance(out, TrendingOutput)
    assert len(out.items) == 1
    assert out.items[0].id == "1"
    assert trending.calls == [30]
