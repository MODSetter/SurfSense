"""Input surface for the TikTok scraper (anonymous, Apify-shaped)."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.schemas import TikTokScrapeInput


def test_input_has_no_auth_fields():
    forbidden = {"username", "password", "token", "login", "auth", "credentials"}
    assert forbidden.isdisjoint(TikTokScrapeInput.model_fields)


def test_input_defaults():
    model = TikTokScrapeInput()
    assert model.resultsPerPage == 1
    assert model.profileSorting == "latest"
    assert model.proxyCountryCode == "None"
    assert model.hashtags == []
    assert model.profiles == []
    assert model.searchQueries == []
    assert model.postURLs == []


def test_input_allows_extra_inert_fields():
    model = TikTokScrapeInput(shouldDownloadVideos=True, videoKvStoreIdOrName="x")
    assert model.model_dump().get("shouldDownloadVideos") is True
