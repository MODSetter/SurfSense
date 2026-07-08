"""End-to-end orchestration over a fake fetch (no network).

Drives the public collector: input -> target -> blob-first flow -> items.
"""

from __future__ import annotations

import json

from app.proprietary.platforms.tiktok import TikTokScrapeInput, scrape_tiktok


def _video_page(video_id: str, username: str) -> str:
    blob = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {
                "itemInfo": {
                    "itemStruct": {
                        "id": video_id,
                        "desc": "hello",
                        "author": {"uniqueId": username},
                        "stats": {"diggCount": 5},
                    }
                }
            }
        }
    }
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        f'type="application/json">{json.dumps(blob)}</script>'
    )


async def test_scrape_video_url_returns_parsed_item():
    url = "https://www.tiktok.com/@scout2015/video/123"

    async def fake_fetch(_url: str) -> str:
        return _video_page("123", "scout2015")

    items = await scrape_tiktok(TikTokScrapeInput(postURLs=[url]), fetch=fake_fetch)

    assert len(items) == 1
    assert items[0]["id"] == "123"
    assert items[0]["diggCount"] == 5
    assert items[0]["webVideoUrl"] == "https://www.tiktok.com/@scout2015/video/123"
    assert items[0]["scrapedAt"] is not None


async def test_scrape_honors_limit_across_targets():
    urls = [
        "https://www.tiktok.com/@a/video/1",
        "https://www.tiktok.com/@b/video/2",
    ]

    async def fake_fetch(url: str) -> str:
        vid = url.rsplit("/", 1)[1]
        user = url.split("@")[1].split("/")[0]
        return _video_page(vid, user)

    items = await scrape_tiktok(
        TikTokScrapeInput(postURLs=urls), limit=1, fetch=fake_fetch
    )
    assert len(items) == 1


async def test_scrape_skips_unrecognized_urls():
    async def fake_fetch(_url: str) -> str:
        return ""

    items = await scrape_tiktok(
        TikTokScrapeInput(postURLs=["https://example.com/x"]), fetch=fake_fetch
    )
    assert items == []
