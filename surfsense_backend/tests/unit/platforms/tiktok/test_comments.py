"""Comments orchestration over a fake fetch (no network).

Drives ``scrape_tiktok_comments``: video URLs -> captured raw comments -> items.
"""

from __future__ import annotations

from typing import Any

from app.proprietary.platforms.tiktok import scrape_tiktok_comments

_VIDEO = "https://www.tiktok.com/@bob/video/123"


def _comment(cid: str, reply_id: str = "0") -> dict[str, Any]:
    return {
        "cid": cid,
        "text": f"comment {cid}",
        "digg_count": 7,
        "reply_comment_total": 2,
        "create_time": 1700000000,
        "reply_id": reply_id,
        "user": {
            "uid": "u1",
            "unique_id": "alice",
            "nickname": "Alice",
            "avatar_thumb": {"url_list": ["https://cdn/a.webp"]},
        },
    }


async def test_comments_parse_dedupe_and_cap():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return [_comment("1"), _comment("1"), _comment("2", reply_id="1")]

    items = await scrape_tiktok_comments(
        [_VIDEO], per_video=2, fetch_comments_fn=fake_fetch
    )

    assert [i["id"] for i in items] == ["1", "2"]
    first = items[0]
    assert first["text"] == "comment 1"
    assert first["videoWebUrl"] == _VIDEO
    assert first["diggCount"] == 7
    assert first["uniqueId"] == "alice"
    assert first["avatar"] == "https://cdn/a.webp"
    assert first["createTimeISO"] is not None
    assert first["repliesToId"] is None  # reply_id "0" == top-level
    assert first["scrapedAt"] is not None
    assert items[1]["repliesToId"] == "1"  # a reply carries its parent id


async def test_empty_video_emits_error_item():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return []

    items = await scrape_tiktok_comments(
        [_VIDEO], per_video=5, fetch_comments_fn=fake_fetch
    )

    assert len(items) == 1
    assert items[0]["errorCode"] == "no_comments"
    assert items[0]["input"] == "123"


async def test_non_video_url_emits_bad_url_error():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        raise AssertionError("should not fetch for a non-video URL")

    items = await scrape_tiktok_comments(
        ["https://www.tiktok.com/@bob"], per_video=5, fetch_comments_fn=fake_fetch
    )

    assert len(items) == 1
    assert items[0]["errorCode"] == "bad_url"


async def test_comments_honor_limit_across_videos():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return [_comment("1"), _comment("2")]

    items = await scrape_tiktok_comments(
        [_VIDEO, "https://www.tiktok.com/@bob/video/456"],
        per_video=5,
        limit=3,
        fetch_comments_fn=fake_fetch,
    )

    assert len(items) == 3
