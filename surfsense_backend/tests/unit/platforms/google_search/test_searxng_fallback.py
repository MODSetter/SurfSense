"""Offline checks for the SearXNG last-resort fallback.

Google is stubbed as fully walled (``fetch_serp_html`` -> ``None``) and the
aggregator's HTTP call is stubbed, so this exercises the real wiring: when the
fallback fires, what it maps, and the cases where it must stay silent.
"""

import pytest

from app.proprietary.platforms.google_search import (
    GoogleSearchScrapeInput,
    scraper,
    searxng,
)

pytestmark = pytest.mark.unit

_PAYLOAD = {
    "results": [
        {
            "title": "Pie Guide",
            "url": "https://pies.example/guide",
            "content": "How to bake.",
        },
        {"title": "No URL here", "content": "dropped"},
    ],
    "suggestions": ["easy pie"],
}


@pytest.fixture
def walled_google(monkeypatch):
    async def _none(url, *, mobile=False):
        return None

    monkeypatch.setattr(scraper, "fetch_serp_html", _none)


@pytest.fixture
def searxng_up(monkeypatch):
    async def _payload(params):
        return _PAYLOAD

    monkeypatch.setattr(searxng, "_HOST", "https://searx.example")
    monkeypatch.setattr(searxng, "_fetch_json", _payload)


async def test_fallback_serves_organic_results(walled_google, searxng_up):
    items = await scraper.scrape_serps(GoogleSearchScrapeInput(queries="apple pie"))

    assert len(items) == 1
    item = items[0]
    # URL-less entries are dropped, and positions stay 1-based and contiguous.
    assert [(r["position"], r["url"]) for r in item["organicResults"]] == [
        (1, "https://pies.example/guide")
    ]
    assert item["organicResults"][0]["description"] == "How to bake."
    assert item["suggestedResults"][0]["title"] == "easy pie"
    # Google-only blocks stay empty rather than being faked.
    assert item["paidResults"] == []
    assert item["peopleAlsoAsk"] == []
    assert item["aiOverview"] is None
    assert item["resultsTotal"] is None
    # Provenance survives to_output() so no consumer can mistake this for Google.
    assert item["resultsProvider"] == "searxng"
    # The provider label, not the configured host.
    assert item["searchQuery"]["domain"] == "searxng"
    assert item["searchQuery"]["term"] == "apple pie"


async def test_fallback_query_folds_only_supported_operators(
    walled_google, monkeypatch
):
    seen: dict = {}

    async def _capture(params):
        seen.update(params)
        return _PAYLOAD

    monkeypatch.setattr(searxng, "_HOST", "https://searx.example")
    monkeypatch.setattr(searxng, "_fetch_json", _capture)

    await scraper.scrape_serps(
        GoogleSearchScrapeInput(
            queries="apple pie",
            site="pies.example",
            forceExactMatch=True,
            wordsInTitle=["easy"],
            fileTypes=["pdf"],
            languageCode="en",
            quickDateRange="w",
        )
    )
    # site: and exact-match survive; intitle:/filetype: would zero out the
    # aggregator's engines, so they are dropped.
    assert seen["q"] == '"apple pie" site:pies.example'
    assert seen["language"] == "en"
    assert seen["time_range"] == "week"


async def test_no_fallback_when_disabled(walled_google, monkeypatch):
    monkeypatch.setattr(searxng, "_HOST", "")
    assert await scraper.scrape_serps(GoogleSearchScrapeInput(queries="q")) == []


async def test_no_fallback_when_ads_requested(walled_google, searxng_up):
    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="car insurance", focusOnPaidAds=True)
    )
    assert items == []


async def test_no_fallback_for_url_without_readable_query(walled_google, searxng_up):
    # A Google URL whose ``q`` cannot be read has no term to re-search.
    items = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="https://www.google.com/search")
    )
    assert items == []


async def test_google_success_is_unstamped_and_untouched(monkeypatch, searxng_up):
    async def _html(url, *, mobile=False):
        return (
            '<html><body><div id="rso">'
            '<div class="tF2Cxc"><a href="https://x.example/a"><h3>Organic</h3></a>'
            "</div></div></body></html>"
        )

    monkeypatch.setattr(scraper, "fetch_serp_html", _html)

    items = await scraper.scrape_serps(GoogleSearchScrapeInput(queries="apple pie"))
    assert len(items) == 1
    assert items[0]["searchQuery"]["domain"] == "google.com"
    assert items[0]["searchQuery"]["url"].startswith("https://www.google.com/search")
    assert "resultsProvider" not in items[0]
