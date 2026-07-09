"""Trending orchestration over a fake fetch (no network).

Drives ``scrape_tiktok_trending``: the Explore feed -> captured itemStructs ->
video items, reusing the listing flow (parse/dedupe/cap/empty-ErrorItem).
"""

from __future__ import annotations

from app.proprietary.platforms.tiktok import scrape_tiktok_trending


async def test_trending_parses_dedupes_and_caps():
    async def fake_fetch(url: str, _cap: int) -> list[dict]:
        assert url == "https://www.tiktok.com/explore"
        return [
            {"id": "1", "author": {"uniqueId": "a"}},
            {"id": "1", "author": {"uniqueId": "a"}},
            {"id": "2", "author": {"uniqueId": "b"}},
        ]

    items = await scrape_tiktok_trending(count=2, fetch_trending_fn=fake_fetch)

    assert [i["id"] for i in items] == ["1", "2"]
    assert items[0]["webVideoUrl"] == "https://www.tiktok.com/@a/video/1"
    assert items[0]["scrapedAt"] is not None


async def test_trending_empty_feed_emits_error_item():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return []

    items = await scrape_tiktok_trending(count=5, fetch_trending_fn=fake_fetch)

    assert len(items) == 1
    assert items[0]["errorCode"] == "no_items"
