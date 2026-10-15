"""What a search sends and stamps, and how a ``site`` filter is enforced.

Google is faked at the scraper's render seam (``fetch_serp_html``) and its
``/goto`` resolver, so these run offline.
"""

import gzip
from pathlib import Path

import pytest

from proprietary.google_search import GoogleSearchScrapeInput, scraper, searxng
from proprietary.google_search.query_builder import (
    build_ai_mode_url,
    build_search_url,
)
from proprietary.google_search.schemas import OrganicResult, SerpItem

FIXTURES = Path(__file__).parent / "fixtures"


def test_no_locale_searches_us_english():
    """Results followed a random exit's language when nothing was sent."""
    url = build_search_url("pie", GoogleSearchScrapeInput(queries="x"))
    assert "gl=us" in url and "hl=en" in url
    ai_mode = build_ai_mode_url("pie", GoogleSearchScrapeInput(queries="x"))
    assert "gl=us" in ai_mode and "hl=en" in ai_mode


@pytest.mark.parametrize(
    ("given", "sent", "absent"),
    [
        ({"countryCode": "FR"}, ["gl=fr"], ["hl="]),
        ({"languageCode": "de"}, ["hl=de"], ["gl="]),
        ({"locationUule": "w+CAIQICIF"}, ["uule="], ["gl=", "hl="]),
    ],
)
def test_any_locale_input_turns_the_default_off(given, sent, absent):
    url = build_search_url("pie", GoogleSearchScrapeInput(queries="x", **given))
    for part in sent:
        assert part in url
    for part in absent:
        assert part not in url


def serp(*hosts: str) -> str:
    """A rendered page whose organic results sit on ``hosts``."""
    blocks = "".join(
        f'<div class="tF2Cxc"><a href="https://{host}/p"><h3>On {host}</h3>'
        f'<cite>https://{host}</cite></a><div class="VwiC3b">About.</div></div>'
        for host in hosts
    )
    return f'<html><body><div id="rso">{blocks}</div></body></html>'


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch):
    """Google serving the queued pages in turn; keeps each rendered URL."""
    pages: list[str] = []
    rendered: list[str] = []

    async def fetch_serp_html(url: str, *, mobile: bool = False) -> str | None:
        rendered.append(url)
        return pages.pop(0) if pages else None

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)
    return pages, rendered


async def test_the_stamp_is_what_was_sent(google):
    pages, _ = google
    pages += [serp("a.example"), serp("a.example"), serp("a.example")]

    [default] = await scraper.scrape_serps(GoogleSearchScrapeInput(queries="pie"))
    [french] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie", countryCode="fr")
    )
    [as_given] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="https://www.google.com/search?q=pie&gl=de")
    )

    assert (
        default["searchQuery"]["countryCode"],
        default["searchQuery"]["languageCode"],
    ) == ("US", "en")
    assert (
        french["searchQuery"]["countryCode"],
        french["searchQuery"]["languageCode"],
    ) == ("FR", None)
    assert (
        as_given["searchQuery"]["countryCode"],
        as_given["searchQuery"]["languageCode"],
    ) == ("DE", None)


async def test_a_fallback_page_claims_no_country(google, monkeypatch):
    async def search_serp(term, input_model, *, page=1):
        return SerpItem(
            organicResults=[OrganicResult(title="Pie", url="https://c.example")],
            resultsProvider="searxng",
        )

    monkeypatch.setattr(searxng, "enabled", lambda: True)
    monkeypatch.setattr(searxng, "search_serp", search_serp)

    [item] = await scraper.scrape_serps(GoogleSearchScrapeInput(queries="pie"))

    assert item["searchQuery"]["countryCode"] is None


@pytest.fixture
def no_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(searxng, "enabled", lambda: False)


async def test_on_site_results_pass_through(google, no_fallback):
    pages, rendered = google
    pages.append(serp("science.nasa.gov", "www.nasa.gov", "go.nasa.gov"))

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="nasa.gov")
    )

    assert len(item["organicResults"]) == 3
    assert len(rendered) == 1


async def test_an_ignored_site_filter_is_rendered_again(google, no_fallback):
    """Seen live: the first render after a /sorry solve dropped site:nasa.gov."""
    pages, rendered = google
    pages += [serp("www.rover.com", "notnasa.gov"), serp("science.nasa.gov")]

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="nasa.gov")
    )

    assert [r["url"] for r in item["organicResults"]] == ["https://science.nasa.gov/p"]
    assert len(rendered) == 2 and rendered[0] == rendered[1]
    assert "site%3Anasa.gov" in rendered[0]


async def test_still_ignored_falls_back_to_searxng(google, monkeypatch):
    pages, rendered = google
    pages += [serp("www.rover.com"), serp("www.rover.com")]
    asked: list[str] = []

    async def search_serp(term, input_model, *, page=1):
        asked.append(input_model.site)
        return SerpItem(
            organicResults=[
                OrganicResult(title="Rover", url="https://mars.nasa.gov/x")
            ],
            resultsProvider="searxng",
        )

    monkeypatch.setattr(searxng, "enabled", lambda: True)
    monkeypatch.setattr(searxng, "search_serp", search_serp)

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="nasa.gov")
    )

    assert item["resultsProvider"] == "searxng"
    assert asked == ["nasa.gov"]
    assert len(rendered) == 2


async def test_off_site_results_never_leave(google, no_fallback, monkeypatch):
    """No fallback either: the page comes back without its off-site results."""
    pages, _ = google
    site_ignored = gzip.decompress(
        (FIXTURES / "serp_site_ignored.html.gz").read_bytes()
    ).decode()
    pages += [site_ignored, site_ignored]

    async def resolve(item, prefetch=None):
        # The capture's links resolve to the hosts their cites print (rover.com…).
        for result in item.organicResults:
            result.url = (result.displayedUrl or "https://www.facebook.com") + "/x"
        return len(item.organicResults)

    monkeypatch.setattr(scraper, "resolve_item_urls", resolve)
    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="nasa.gov")
    )

    assert item["organicResults"] == []
    assert item.get("resultsProvider") is None
    # Nor the rest of the unfiltered page: its count, ads, PAA and overview.
    assert scraper.parse_serp(site_ignored).resultsTotal == 420_000_000
    for field in ("resultsTotal", "paidResults", "peopleAlsoAsk", "aiOverview"):
        assert not item.get(field), field


async def test_the_retry_can_be_turned_off(google, no_fallback, monkeypatch):
    pages, rendered = google
    pages += [serp("www.rover.com"), serp("science.nasa.gov")]
    monkeypatch.setattr(scraper, "_SITE_RETRIES", 0)

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="https://www.nasa.gov/")
    )

    assert item["organicResults"] == []
    assert len(rendered) == 1


async def test_unresolved_links_are_judged_by_their_cite(
    google, no_fallback, monkeypatch
):
    """A /goto link that did not resolve is on-site when its cite says so, and
    one with no cite at all is kept once the filter is known to be applied."""
    pages, rendered = google
    pages.append(
        '<html><body><div id="rso">'
        '<div class="tF2Cxc"><a href="/goto?url=1"><h3>A</h3>'
        "<cite>https://www.nasa.gov</cite></a></div>"
        '<div class="tF2Cxc"><a href="/goto?url=2"><h3>B</h3>'
        "<cite>12 comments · 2 days ago</cite></a></div>"
        "</div></body></html>"
    )

    async def resolve(item, prefetch=None):
        return 0

    monkeypatch.setattr(scraper, "resolve_item_urls", resolve)
    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="mars rover", site="nasa.gov")
    )

    assert [r["title"] for r in item["organicResults"]] == ["A", "B"]
    assert len(rendered) == 1
