"""Offline tests for Google-backed Instagram discovery.

Discovery is profile-only (hashtag/place feeds are login-walled). A valid handle
resolves directly; any other query falls back to the ``google_search`` platform
(``site:instagram.com``), classifying organic results with ``resolve_url`` and
keeping only profile hits. These tests inject a fake ``scrape_serps`` so there is
no network: they pin the classification, de-dup, and ``limit`` cap.
"""

from __future__ import annotations

from app.proprietary.platforms.instagram import scraper


def _fake_serps(*organic_urls: str):
    async def _scrape_serps(input_model, *, limit=None):
        assert input_model.site == "instagram.com"
        return [{"organicResults": [{"url": u} for u in organic_urls]}]

    return _scrape_serps


async def test_google_discovery_keeps_only_profiles(monkeypatch):
    # A non-handle query goes to Google; only profile URLs survive (hashtag /
    # post / non-instagram results are dropped since discovery is profile-only).
    monkeypatch.setattr(
        scraper,
        "scrape_serps",
        _fake_serps(
            "https://www.instagram.com/natgeo/",
            "https://www.instagram.com/explore/tags/travel/",
            "https://www.instagram.com/p/ABC123/",
            "https://example.com/not-instagram",
        ),
    )
    targets = await scraper._discover("nat geo photos", search_type="profile", limit=10)
    assert [(t.kind, t.value) for t in targets] == [("profile", "natgeo")]


async def test_google_discovery_dedupes(monkeypatch):
    monkeypatch.setattr(
        scraper,
        "scrape_serps",
        _fake_serps(
            "https://www.instagram.com/natgeo/",
            "https://www.instagram.com/natgeo/",
        ),
    )
    targets = await scraper._discover("nat geo photos", search_type="profile", limit=10)
    assert len(targets) == 1


async def test_google_discovery_respects_limit(monkeypatch):
    monkeypatch.setattr(
        scraper,
        "scrape_serps",
        _fake_serps(
            "https://www.instagram.com/a_a/",
            "https://www.instagram.com/b_b/",
            "https://www.instagram.com/c_c/",
        ),
    )
    targets = await scraper._discover("some brand name", search_type="profile", limit=2)
    assert [t.value for t in targets] == ["a_a", "b_b"]


async def test_discover_profile_handle_fast_path_skips_google(monkeypatch):
    # A valid handle resolves directly without touching Google.
    async def _boom(input_model, *, limit=None):
        raise AssertionError("Google should not be called for a valid handle")

    monkeypatch.setattr(scraper, "scrape_serps", _boom)
    targets = await scraper._discover("messi", search_type="user", limit=10)
    assert [(t.kind, t.value) for t in targets] == [("profile", "messi")]
