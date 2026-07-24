"""User-search orchestration over a fake fetch (no network).

Drives ``search_tiktok_users``: queries -> captured ``user_info`` -> profile items.
"""

from __future__ import annotations

from typing import Any

from app.proprietary.platforms.tiktok import search_tiktok_users


def _user(uid: str, unique_id: str, followers: int = 10) -> dict[str, Any]:
    return {
        "uid": uid,
        "unique_id": unique_id,
        "nickname": unique_id.upper(),
        "signature": "bio",
        "follower_count": followers,
        "total_favorited": 999,
        "sec_uid": f"sec-{uid}",
        "enterprise_verify_reason": "official" if uid == "1" else "",
        "avatar_thumb": {"url_list": [f"https://cdn/{uid}.webp"]},
    }


async def test_user_search_parses_dedupes_and_caps():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return [_user("1", "nasa"), _user("1", "nasa"), _user("2", "nasa2")]

    items = await search_tiktok_users(["nasa"], per_query=2, fetch_users=fake_fetch)

    assert [i["id"] for i in items] == ["1", "2"]
    first = items[0]
    assert first["name"] == "nasa"
    assert first["nickName"] == "NASA"
    assert first["profileUrl"] == "https://www.tiktok.com/@nasa"
    assert first["verified"] is True
    assert first["fans"] == 10
    assert first["avatar"] == "https://cdn/1.webp"
    assert first["secUid"] == "sec-1"
    assert first["scrapedAt"] is not None
    assert items[1]["verified"] is False


async def test_user_search_empty_query_emits_error_item():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return []

    items = await search_tiktok_users(["ghost"], per_query=5, fetch_users=fake_fetch)

    assert len(items) == 1
    assert items[0]["errorCode"] == "no_users"
    assert items[0]["input"] == "ghost"


async def test_user_search_honors_limit_across_queries():
    async def fake_fetch(_url: str, _cap: int) -> list[dict]:
        return [_user("1", "a"), _user("2", "b")]

    items = await search_tiktok_users(
        ["q1", "q2"], per_query=5, limit=3, fetch_users=fake_fetch
    )

    # 2 from q1 + 1 from q2, then the cross-query limit stops it.
    assert len(items) == 3
