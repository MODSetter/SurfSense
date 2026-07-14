"""Offline budget tests: per-target caps, cross-target de-dup, and the limit guard.

No network. ``fetch_json`` is stubbed with a synthetic profile payload and the
fan-out proxy holders are replaced with no-ops, so the orchestrator's paging and
de-dup policy is exercised deterministically.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.proprietary.platforms.instagram import scraper
from app.proprietary.platforms.instagram.schemas import InstagramScrapeInput


class _NoopHolder:
    async def close(self) -> None:
        return None


@pytest.fixture
def _stub_proxy(monkeypatch):
    async def _open():
        return _NoopHolder()

    @asynccontextmanager
    async def _bind(_holder):
        yield _holder

    monkeypatch.setattr(scraper, "open_proxy_holder", _open)
    monkeypatch.setattr(scraper, "bind_proxy_holder", _bind)


def _profile_payload(n: int) -> dict:
    return {
        "data": {
            "user": {
                "id": "9",
                "username": "acct",
                "edge_owner_to_timeline_media": {
                    "count": n,
                    "edges": [
                        {"node": {"id": str(i), "shortcode": f"S{i}"}} for i in range(n)
                    ],
                },
            }
        }
    }


async def test_per_target_cap_limits_media(_stub_proxy, monkeypatch):
    async def _fetch(path, params=None):
        return _profile_payload(50)

    monkeypatch.setattr(scraper, "fetch_json", _fetch)
    model = InstagramScrapeInput(
        resultsType="posts",
        directUrls=["https://www.instagram.com/acct/"],
        resultsLimit=5,
    )
    items = [i async for i in scraper.iter_instagram(model)]
    assert len(items) == 5


async def test_cross_target_dedup_by_id(_stub_proxy, monkeypatch):
    async def _fetch(path, params=None):
        return _profile_payload(3)  # both targets return ids 0,1,2

    monkeypatch.setattr(scraper, "fetch_json", _fetch)
    model = InstagramScrapeInput(
        resultsType="posts",
        directUrls=[
            "https://www.instagram.com/one/",
            "https://www.instagram.com/two/",
        ],
        resultsLimit=10,
    )
    items = [i async for i in scraper.iter_instagram(model)]
    ids = sorted(i["id"] for i in items)
    assert ids == ["0", "1", "2"]


async def test_scrape_instagram_honors_limit(_stub_proxy, monkeypatch):
    async def _fetch(path, params=None):
        return _profile_payload(50)

    monkeypatch.setattr(scraper, "fetch_json", _fetch)
    model = InstagramScrapeInput(
        resultsType="posts",
        directUrls=["https://www.instagram.com/acct/"],
        resultsLimit=100,
    )
    items = await scraper.scrape_instagram(model, limit=7)
    assert len(items) == 7
