"""URL classification for the TikTok scraper (pure, no network)."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.targets import resolve_target


def test_resolve_video_carries_username_and_id():
    target = resolve_target(
        "https://www.tiktok.com/@scout2015/video/6718335390845095173"
    )
    assert target is not None
    assert target.kind == "video"
    assert target.value == "6718335390845095173"
    assert target.username == "scout2015"


def test_resolve_profile():
    target = resolve_target("https://www.tiktok.com/@scout2015")
    assert target is not None
    assert target.kind == "profile"
    assert target.value == "scout2015"


def test_resolve_hashtag():
    target = resolve_target("https://www.tiktok.com/tag/funny")
    assert target is not None
    assert target.kind == "hashtag"
    assert target.value == "funny"


def test_resolve_search_top_video_and_user_sections():
    top = resolve_target("https://www.tiktok.com/search?q=cats")
    assert top is not None
    assert top.kind == "search"
    assert top.value == "cats"
    assert top.section is None

    videos = resolve_target("https://www.tiktok.com/search/video?q=cats")
    assert videos is not None and videos.section == "video"

    users = resolve_target("https://www.tiktok.com/search/user?q=cats")
    assert users is not None and users.section == "user"


def test_resolve_rejects_non_tiktok_and_unknown_paths():
    assert resolve_target("https://example.com/@scout2015") is None
    assert resolve_target("https://www.tiktok.com/") is None
    assert resolve_target("https://www.tiktok.com/foundation") is None
