"""Offline tests for Google-backed TikTok video discovery.

``searchQueries`` are login-walled on TikTok's native search, so they route
through the ``google_search`` platform (``site:tiktok.com``): each organic URL
is classified with ``resolve_target`` and only video hits (``/@user/video/<id>``)
are kept — profiles/hashtags/search/photo/non-tiktok are dropped (accounts
belong to the user-search verb). These tests inject a fake ``scrape_serps`` so
there is no network: they pin the classification, cross-query de-dup, the limit
cap, the barren-query ErrorItem, and that no ``/search?q=`` listing target is
ever built.
"""

from __future__ import annotations

import json

from app.proprietary.platforms.tiktok import (
    TikTokScrapeInput,
    orchestrator,
    scrape_tiktok,
)


def _fake_serps(*organic_urls: str):
    async def _scrape_serps(input_model, *, limit=None):
        assert input_model.site == "tiktok.com"
        assert input_model.maxPagesPerQuery == 1
        return [{"organicResults": [{"url": u} for u in organic_urls]}]

    return _scrape_serps


def _video_page(url: str) -> str:
    """Render a rehydration blob for a ``/@user/video/<id>`` URL."""
    video_id = url.rsplit("/", 1)[1]
    username = url.split("@")[1].split("/")[0]
    blob = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {
                "itemInfo": {
                    "itemStruct": {
                        "id": video_id,
                        "desc": "hi",
                        "author": {"uniqueId": username},
                        "stats": {"diggCount": 1},
                    }
                }
            }
        }
    }
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        f'type="application/json">{json.dumps(blob)}</script>'
    )


async def _fetch_video(url: str) -> str:
    return _video_page(url)


async def test_search_discovery_keeps_only_videos(monkeypatch):
    # Only the video URL survives; profile / hashtag / search / photo /
    # non-tiktok organic results are dropped.
    monkeypatch.setattr(
        orchestrator,
        "scrape_serps",
        _fake_serps(
            "https://www.tiktok.com/@nasa/video/123",
            "https://www.tiktok.com/@nasa",
            "https://www.tiktok.com/tag/space",
            "https://www.tiktok.com/search?q=space",
            "https://www.tiktok.com/@nasa/photo/999",
            "https://example.com/not-tiktok",
        ),
    )
    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=["space"], resultsPerPage=10),
        fetch=_fetch_video,
    )
    assert [i["id"] for i in items] == ["123"]


async def test_search_discovery_dedupes_across_queries(monkeypatch):
    # The same video surfacing under two queries is scraped once.
    monkeypatch.setattr(
        orchestrator,
        "scrape_serps",
        _fake_serps("https://www.tiktok.com/@nasa/video/123"),
    )
    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=["space", "rockets"], resultsPerPage=10),
        fetch=_fetch_video,
    )
    assert [i["id"] for i in items] == ["123"]


async def test_search_discovery_respects_per_target_limit(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "scrape_serps",
        _fake_serps(
            "https://www.tiktok.com/@a/video/1",
            "https://www.tiktok.com/@b/video/2",
            "https://www.tiktok.com/@c/video/3",
        ),
    )
    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=["x"], resultsPerPage=2),
        fetch=_fetch_video,
    )
    assert [i["id"] for i in items] == ["1", "2"]


async def test_search_barren_query_emits_error_item(monkeypatch):
    # A query whose discovery finds no video URLs degrades to one ErrorItem.
    monkeypatch.setattr(
        orchestrator,
        "scrape_serps",
        _fake_serps(
            "https://www.tiktok.com/@nasa",
            "https://example.com/x",
        ),
    )
    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=["space"], resultsPerPage=10),
        fetch=_fetch_video,
    )
    assert len(items) == 1
    assert items[0]["errorCode"] == "no_items"
    assert items[0]["input"] == "space"


async def test_search_never_builds_listing_target(monkeypatch):
    # searchQueries must never hit the (login-walled) native search listing flow.
    monkeypatch.setattr(
        orchestrator,
        "scrape_serps",
        _fake_serps("https://www.tiktok.com/@nasa/video/123"),
    )

    async def _boom_listing(_url: str, _count: int) -> list[dict]:
        raise AssertionError("searchQueries must not build a listing target")

    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=["space"], resultsPerPage=10),
        fetch=_fetch_video,
        fetch_listing=_boom_listing,
    )
    assert [i["id"] for i in items] == ["123"]
