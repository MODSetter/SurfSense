"""The Google Search plugin as the app reaches it: its MCP server on the host, behind the license.

Google is faked at the scraper's render seam, `fetch_serp_html`, and SearXNG at
`search_serp`; the host, the license check, the tool and the SERP parsing are real.
"""

import importlib
import json
from collections.abc import Iterator
from types import ModuleType
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.google_search import scraper, searxng
from proprietary.google_search.schemas import OrganicResult, SerpItem
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def google_search(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Google Search plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        # The host enters the plugin's lifespan; no Chromium launch in tests.
        monkeypatch.setenv("GOOGLE_SEARCH_WARM_BROWSER", "0")
        with serving(host_app(plugins={"google-search"})) as base:
            yield f"{base}/google-search/mcp"


def serp(term: str) -> str:
    """A rendered results page with two organic results, as Google's DOM marks them."""
    return f"""
    <html><body><div id="rso">
      <div class="tF2Cxc"><a href="https://a.example/{term}"><h3>{term} guide</h3>
        <cite>a.example</cite></a><div class="VwiC3b">All about {term}.</div></div>
      <div class="tF2Cxc"><a href="https://b.example/{term}"><h3>{term} tips</h3>
        <cite>b.example</cite></a><div class="VwiC3b">More on {term}.</div></div>
    </div></body></html>
    """


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Google answering every render; keeps each URL rendered."""
    rendered: list[str] = []

    async def fetch_serp_html(url: str, *, mobile: bool = False) -> str:
        rendered.append(url)
        term = "pie" if "pie" in url else "cake"
        return serp(term)

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)
    return rendered


@pytest.fixture
def walled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Google walling every address the render tries."""

    async def fetch_serp_html(url: str, *, mobile: bool = False) -> None:
        return None

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)


async def test_it_offers_one_read_only_tool_that_reaches_the_web(
    google_search: str,
) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(google_search, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert [tool.name for tool in tools] == ["scrape"]
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True
    assert tools[0].annotations.open_world_hint is True


async def test_a_search_returns_its_pages_as_text_and_progress(
    google_search: str, google: list[str]
) -> None:
    progress: list[float] = []

    result = await call(
        google_search,
        "scrape",
        {"queries": ["apple pie", "cheesecake"], "country_code": "fr"},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["searchQuery"]["term"] for item in items] == [
        "apple pie",
        "cheesecake",
    ]
    assert [r["url"] for r in items[0]["organicResults"]] == [
        "https://a.example/pie",
        "https://b.example/pie",
    ]
    assert "gl=fr" in google[0]
    # The text carries each page's results, not only titles: opencode keeps
    # just the text, so the agent reads descriptions and answers from it.
    header, *lines = result.content[0].text.splitlines()
    assert header.startswith("2 Google results pages")
    pie, cake = (json.loads(line) for line in lines)
    assert pie["query"] == "apple pie"
    assert pie["organic"][0] == {
        "position": 1,
        "title": "pie guide",
        "url": "https://a.example/pie",
        "description": "All about pie.",
    }
    assert cake["organic"][1]["url"] == "https://b.example/cake"
    # Stage progress: rising, ending at both pages done (the limiter may drop
    # the stages in between).
    assert progress == sorted(set(progress))
    assert progress[0] < 1 and progress[-1] == 2


def _measured_page(term: str) -> dict:
    """A page-1 item sized as measured live: ten results, six long PAA answers
    and a 3k-character AI Overview (a 9-15 KB line before the clips)."""
    return {
        "searchQuery": {"term": term, "page": 1},
        "resultsTotal": 1_230_000,
        "organicResults": [
            {
                "position": i,
                "title": f"{term} result {i}",
                "url": f"https://site{i}.example/{term}",
                "description": "d" * 150,
                "date": "Jul 2, 2026",
            }
            for i in range(1, 11)
        ],
        "peopleAlsoAsk": [
            {
                "question": f"Why {term} {i}?",
                "answer": "a" * 1500,
                "url": "https://p.example/",
            }
            for i in range(6)
        ],
        "aiOverview": {
            "content": "o" * 2900,
            "sources": [
                {"title": f"s{i}", "url": f"https://s{i}.example/"} for i in range(8)
            ],
        },
        "paidResults": [
            {"title": "ad", "url": "https://ad.example/", "description": "buy"}
        ],
        "relatedQueries": [{"title": f"{term} more {i}"} for i in range(8)],
    }


@pytest.fixture
def measured(google_search: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Google serving measured pages; returns the plugin's server module."""

    async def fetch_serp_html(url: str, *, mobile: bool = False) -> str:
        return parse_qs(urlsplit(url).query)["q"][0]  # the "HTML" is the term

    def parse_serp(term: str, **kwargs) -> SerpItem:
        return SerpItem.model_validate(_measured_page(term))

    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)
    monkeypatch.setattr(scraper, "parse_serp", parse_serp)
    # Imported once the license env is set: the module reads it on import.
    return importlib.import_module("proprietary.google_search.server")


async def test_a_few_pages_keep_their_answers_opening(
    google_search: str, measured: ModuleType
) -> None:
    result = await call(google_search, "scrape", {"queries": ["pie", "cake"]}, LICENSE)

    _, *lines = result.content[0].text.splitlines()
    assert len(lines) == 2
    pie = json.loads(lines[0])
    assert len(pie["peopleAlsoAsk"]) == 6
    assert len(pie["peopleAlsoAsk"][0]["answer"]) == measured.PAA_ANSWER_CHARS + 1
    assert len(pie["aiOverview"]["text"]) == measured.CLIP_CHARS + 1
    assert pie["ads"] and pie["organic"][0]["date"] == "Jul 2, 2026"


async def test_every_page_of_a_many_page_call_reaches_the_text(
    google_search: str, measured: ModuleType
) -> None:
    """A third page-1 line used to fall out of the 32 KB text, so a text-only
    client lost whole queries; past three pages each is listed compactly."""
    terms = [f"query {n}" for n in range(10)]
    result = await call(google_search, "scrape", {"queries": terms}, LICENSE)

    header, *lines = result.content[0].text.splitlines()
    assert header.startswith("10 Google results pages")
    assert [json.loads(line)["query"] for line in lines] == terms
    first = json.loads(lines[0])
    assert first["peopleAlsoAsk"][0] == "Why query 0 0?"
    assert len(first["aiOverview"]) == measured.COMPACT_OVERVIEW_CHARS + 1
    assert first["organic"][0] == {
        "title": "query 0 result 1",
        "url": "https://site1.example/query 0",
        "description": "d" * 150,
    }
    assert len(first["organic"]) == 10 and "ads" not in first


async def test_more_pages_of_one_query_are_each_an_item(
    google_search: str, google: list[str]
) -> None:
    result = await call(
        google_search,
        "scrape",
        {"queries": ["apple pie"], "max_pages_per_query": 2},
        LICENSE,
    )

    pages = [item["searchQuery"]["page"] for item in result.structured_content["items"]]
    assert pages == [1, 2]
    assert "start=10" in google[1]


async def test_a_fallback_page_says_it_is_not_google_s(
    google_search: str, walled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So the agent never reports an aggregator's order as Google's ranking."""

    async def search_serp(term, input_model, *, page=1):
        return SerpItem(
            organicResults=[OrganicResult(title="Pie", url="https://c.example")],
            resultsProvider="searxng",
        )

    monkeypatch.setattr(searxng, "enabled", lambda: True)
    monkeypatch.setattr(searxng, "search_serp", search_serp)

    result = await call(google_search, "scrape", {"queries": ["apple pie"]}, LICENSE)

    assert not result.is_error
    assert result.structured_content["items"][0]["resultsProvider"] == "searxng"
    assert "SearXNG" in result.content[0].text


async def test_google_walling_every_address_reads_as_the_tool_s_error(
    google_search: str, walled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not as no results: the agent may try again later."""
    monkeypatch.setattr(searxng, "enabled", lambda: False)

    result = await call(google_search, "scrape", {"queries": ["apple pie"]}, LICENSE)

    assert result.is_error
    assert "Google" in result.content[0].text


async def test_a_page_to_read_is_refused_rather_than_searched_for(
    google_search: str, google: list[str]
) -> None:
    """An agent wanting a page's text would otherwise pay a render for its URL as a term."""
    result = await call(
        google_search,
        "scrape",
        {"queries": ["apple pie", "https://www.gadgets360.com/audio/guide/best-anc"]},
        LICENSE,
    )

    assert result.is_error
    assert "gadgets360.com" in result.content[0].text
    assert "Web Crawl" in result.content[0].text
    assert google == []


async def test_a_google_search_url_is_scraped_as_it_is(
    google_search: str, google: list[str]
) -> None:
    result = await call(
        google_search,
        "scrape",
        {"queries": ["https://www.google.com/search?q=apple+pie&gl=de"]},
        LICENSE,
    )

    assert not result.is_error
    assert google == ["https://www.google.com/search?q=apple+pie&gl=de"]


async def test_a_call_naming_nothing_to_search_is_refused(google_search: str) -> None:
    result = await call(google_search, "scrape", {"queries": []}, LICENSE)

    assert result.is_error


def test_without_a_license_the_plugin_answers_nothing(google_search: str) -> None:
    refused = httpx2.post(google_search, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
