"""Parser fixes pinned on real SERPs captured live in Oct 2026.

The fixtures are those captures trimmed to what the parser reads (no scripts,
styles, data images or tracking attributes; each ``/goto`` blob replaced by a
short stand-in, session tokens by ``x``) and gzipped. They pin the data bugs the profiling run found:
page 2's result count, dates ending in a dash, star ratings read as dates,
"Read more" in descriptions, empty AI Overview sources and missing displayed
URLs on forum cards.
"""

import gzip
import re
from pathlib import Path

import pytest

from proprietary.google_search import GoogleSearchScrapeInput, scraper
from proprietary.google_search.parsers import GOTO_PREFIX, parse_serp

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = [
    "serp_best_running_shoes",
    "serp_climate_change",
    "serp_github",
    "serp_python",
    "serp_python_page2",
    "serp_site_ignored",
]
_DASHES = ("\N{MIDDLE DOT}", "-", "\N{EN DASH}", "\N{EM DASH}")


def capture(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes()).decode()


@pytest.mark.parametrize("name", PAGES)
def test_captures_keep_no_session_tokens(name: str):
    """sxsrf and sstk are the session's tokens, ei and ved its request ids."""
    found = re.findall(r"[?&;](sxsrf|sstk|ei|ved)=([^&\"'\s<>]*)", capture(name))
    assert {param for param, _ in found} >= {"sxsrf", "ei", "ved"}
    assert {value for _, value in found} == {"x"}


def test_page_two_counts_results_not_its_page_number():
    """'Page 2 of about 467 results' read as 2."""
    assert parse_serp(capture("serp_python_page2")).resultsTotal == 467
    assert parse_serp(capture("serp_climate_change")).resultsTotal == 191


@pytest.mark.parametrize(
    ("stats", "total"),
    [
        ("Page 3 of about 1,230 results (0.38s)", 1230),
        ("Seite 2 von ungefähr 1.230.000 Ergebnissen (0,41 Sekunden)", 1230000),
        ("Environ 12\N{NARROW NO-BREAK SPACE}345 résultats (0,30 s)", 12345),
        ("Ungefähr 1\N{NO-BREAK SPACE}230 Ergebnisse", 1230),
        ("About 1'230 results", 1230),
        ("1 result", 1),
        ("About 21 results (0.45 seconds)", 21),
        # ja and zh write the timing in full-width parentheses (U+FF08, U+FF09).
        (
            "約 1,230,000 件 \N{FULLWIDTH LEFT PARENTHESIS}0.45 秒\N{FULLWIDTH RIGHT PARENTHESIS}",
            1230000,
        ),
        (
            "約 1,230,000 件中 2 ページ目 \N{FULLWIDTH LEFT PARENTHESIS}0.45 秒\N{FULLWIDTH RIGHT PARENTHESIS}",
            1230000,
        ),
        (
            "2 ページ目 (約 1,230,000 件) \N{FULLWIDTH LEFT PARENTHESIS}0.51 秒\N{FULLWIDTH RIGHT PARENTHESIS}",
            1230000,
        ),
        (
            "找到约 25,270,000 条结果 \N{FULLWIDTH LEFT PARENTHESIS}用时 0.32 秒\N{FULLWIDTH RIGHT PARENTHESIS}",
            25270000,
        ),
        (
            "获得约 25,270,000 条结果\N{FULLWIDTH COMMA}以下是第 2 页 \N{FULLWIDTH LEFT PARENTHESIS}用时 0.35 秒\N{FULLWIDTH RIGHT PARENTHESIS}",
            25270000,
        ),
    ],
)
def test_result_count_reads_every_grouping(stats: str, total: int):
    html = f'<html><body><div id="result-stats">{stats}</div></body></html>'
    assert parse_serp(html).resultsTotal == total


@pytest.mark.parametrize("name", PAGES)
def test_dates_are_dates_and_descriptions_are_clean(name: str):
    for result in parse_serp(capture(name)).organicResults:
        if result.date is not None:
            assert not result.date.endswith(_DASHES), result.date
            assert not re.fullmatch(r"[\d.,()\s]+", result.date), result.date
        description = result.description or ""
        assert not description.startswith(_DASHES), description
        assert not description.endswith("Read more"), description


def test_dated_results_keep_their_date_and_ratings_are_not_dates():
    climate = parse_serp(capture("serp_climate_change")).organicResults
    assert [r.date for r in climate[1:3]] == ["Jul 23, 2026", "Sep 24, 2025"]
    assert climate[1].description.startswith("Climate change is fueling")

    shoes = {
        r.displayedUrl: r
        for r in parse_serp(capture("serp_best_running_shoes")).organicResults
    }
    # Nike and REI carry a store rating ("4.7", "4.8") in a YrbPuc span.
    assert shoes["https://www.nike.com"].date is None
    assert shoes["https://www.rei.com"].date is None
    assert shoes["https://runrepeat.com"].date == "Sep 12, 2026"
    assert shoes["https://runrepeat.com"].description.endswith("responsiveness ...")


@pytest.mark.parametrize(
    ("inner", "date"),
    [
        ("<span>3 days ago</span> \N{EM DASH} ", "3 days ago"),
        (
            "<span>hace 3 d\N{LATIN SMALL LETTER I WITH ACUTE}as</span> \N{MIDDLE DOT} ",
            "hace 3 d\N{LATIN SMALL LETTER I WITH ACUTE}as",
        ),
        ("<span>23 juil. 2026</span> \N{EN DASH} ", "23 juil. 2026"),
        ("4.7", None),
        ("(57)", None),
    ],
)
def test_a_date_in_any_language_but_never_a_rating(inner: str, date: str | None):
    html = (
        '<html><body><div id="rso"><div class="tF2Cxc">'
        '<a href="https://x.example/a"><h3>T</h3></a>'
        f'<div class="VwiC3b"><span class="YrbPuc">{inner}</span>'
        "<span>Snippet.</span></div></div></div></body></html>"
    )
    [result] = parse_serp(html).organicResults
    assert result.date == date
    if date:
        assert result.description == "Snippet."


@pytest.mark.parametrize(
    ("name", "at_least"),
    [("serp_climate_change", 10), ("serp_python", 15), ("serp_best_running_shoes", 6)],
)
def test_ai_overview_lists_its_sources(name: str, at_least: int):
    sources = parse_serp(capture(name)).aiOverview.sources
    assert len(sources) >= at_least
    assert len({s.url for s in sources}) == len(sources)
    # Most cite through /goto; video sources link YouTube directly.
    assert sum(s.url.startswith(GOTO_PREFIX) for s in sources) >= 6
    for source in sources:
        assert source.title and not source.title.endswith("Opens in new tab.")
        assert source.url.startswith("https://")
        assert source.description
        # The site icon is an inline data URI, not an image URL.
        assert not (source.imageUrl or "").startswith("data:")


def test_ai_overview_source_fields():
    first = parse_serp(capture("serp_climate_change")).aiOverview.sources[0]
    assert first.title == "What Is Climate Change? | United Nations"
    assert first.site == "Welcome to the United Nations"
    assert first.description.startswith("Definition: Long-term temperature")


def test_brand_result_keeps_its_sitelinks():
    first = parse_serp(capture("serp_github")).organicResults[0]
    assert first.displayedUrl == "https://github.com"
    assert len(first.siteLinks) == 5


async def test_forum_cards_get_their_host_as_displayed_url(monkeypatch):
    """The reddit card's cite is '220+ comments · 4 months ago', not a URL."""

    async def fetch(url, *, mobile=False):
        return capture("serp_best_running_shoes")

    async def resolve(item, prefetch=None):
        for result in item.organicResults:
            if result.displayedUrl is None:
                result.url = "https://www.reddit.com/r/runninglifestyle/comments/x"
            else:
                result.url = result.displayedUrl + "/page"
        return len(item.organicResults)

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch)
    monkeypatch.setattr(scraper, "resolve_item_urls", resolve)

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="best running shoes")
    )

    reddit = item["organicResults"][2]
    assert reddit["url"].startswith("https://www.reddit.com/")
    assert reddit["displayedUrl"] == "https://www.reddit.com"
    # A cite that already was a URL is left as Google printed it.
    assert item["organicResults"][0]["displayedUrl"] == "https://runrepeat.com"


async def test_an_unresolved_link_gets_no_google_host(monkeypatch):
    async def fetch(url, *, mobile=False):
        return capture("serp_best_running_shoes")

    async def resolve(item, prefetch=None):
        return 0

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch)
    monkeypatch.setattr(scraper, "resolve_item_urls", resolve)

    [item] = await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="best running shoes")
    )

    assert item["organicResults"][2]["displayedUrl"] is None
