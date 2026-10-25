"""Offline budget tests: per-target caps, cross-target de-dup, and the limit guard.

No network. ``fetch_html`` serves built profile pages and the fan-out proxy
holders are replaced with no-ops, so the orchestrator's paging and de-dup policy
is exercised deterministically.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from proprietary.instagram import scraper
from proprietary.instagram.schemas import InstagramScrapeInput
from proprietary.instagram.tests.profile_pages import profile_pages


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


def _serve(monkeypatch, n: int) -> None:
    """Every profile with posts 0..n-1, the same ids for each."""

    async def _fetch(path, params=None):
        username = path.split("/", 1)[0]
        return profile_pages(username, list(range(n))).get(path)

    monkeypatch.setattr(scraper, "fetch_html", _fetch)


async def test_per_target_cap_limits_media(_stub_proxy, monkeypatch):
    _serve(monkeypatch, 50)
    model = InstagramScrapeInput(
        resultsType="posts",
        directUrls=["https://www.instagram.com/acct/"],
        resultsLimit=5,
    )
    items = [i async for i in scraper.iter_instagram(model)]
    assert len(items) == 5


async def test_cross_target_dedup_by_id(_stub_proxy, monkeypatch):
    _serve(monkeypatch, 3)  # both targets return ids m0, m1, m2
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
    assert ids == ["m0", "m1", "m2"]


async def test_scrape_instagram_honors_limit(_stub_proxy, monkeypatch):
    _serve(monkeypatch, 50)
    model = InstagramScrapeInput(
        resultsType="posts",
        directUrls=["https://www.instagram.com/acct/"],
        resultsLimit=100,
    )
    items = await scraper.scrape_instagram(model, limit=7)
    assert len(items) == 7
