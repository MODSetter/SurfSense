"""Offline tests for multi-search budgeting in ``iter_reddit``.

No network: ``_search_flow`` is faked. Asserts the maxItems budget is
fair-shared across concurrent searches (a noisy query can't starve the rest)
and that the same post surfacing via several queries is emitted once.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.proprietary.platforms.reddit import scraper
from app.proprietary.platforms.reddit.schemas import RedditScrapeInput


def _fake_search_flow(results_by_query: dict[str, list[str]]):
    """Fake flow yielding post dicts (id per entry), honoring ``max_items``."""
    calls: dict[str, int] = {}

    def flow(
        query: str,
        *,
        input_model: RedditScrapeInput,
        subreddit: str | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        cap = input_model.maxItems if max_items is None else max_items
        calls[query] = cap

        async def gen() -> AsyncIterator[dict]:
            for pid in results_by_query.get(query, [])[:cap]:
                yield {"dataType": "post", "id": pid, "title": pid}

        return gen()

    return flow, calls


async def test_budget_is_fair_shared_across_searches(monkeypatch):
    # One noisy query with 100 hits must not starve the two precise ones.
    data = {
        "noisy": [f"n{i}" for i in range(100)],
        "precise_a": ["a1", "a2", "a3"],
        "precise_b": ["b1", "b2"],
    }
    flow, calls = _fake_search_flow(data)
    monkeypatch.setattr(scraper, "_search_flow", flow)

    model = RedditScrapeInput(searches=list(data), maxItems=30)
    items = await scraper.scrape_reddit(model, limit=30)

    ids = {i["id"] for i in items}
    # Every precise result made it in; noisy filled only its ceil(30/3)=10 share.
    assert {"a1", "a2", "a3", "b1", "b2"} <= ids
    assert sum(1 for i in ids if i.startswith("n")) == 10
    assert all(cap == 10 for cap in calls.values())


async def test_duplicate_posts_across_searches_emit_once(monkeypatch):
    data = {"q1": ["dup", "x1"], "q2": ["dup", "x2"]}
    flow, _ = _fake_search_flow(data)
    monkeypatch.setattr(scraper, "_search_flow", flow)

    model = RedditScrapeInput(searches=["q1", "q2"], maxItems=10)
    items = await scraper.scrape_reddit(model, limit=10)

    ids = [i["id"] for i in items]
    assert ids.count("dup") == 1
    assert {"x1", "x2"} <= set(ids)
