"""The Google Search plugin as the app reaches it: its MCP server on the host, behind the license.

Google is faked at the scraper's render seam, `fetch_serp_html`, and SearXNG at
`search_serp`; the host, the license check, the tool and the SERP parsing are real.
"""

from collections.abc import Iterator

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.google_search import scraper, searxng
from proprietary.google_search.schemas import OrganicResult, SerpItem
from proprietary.license_check import keygen
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def google_search(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Google Search plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setattr(keygen, "KEYGEN_API_URL", keygen_url)
        monkeypatch.setattr(keygen, "SURFSENSE_ACCOUNT_ID", ACCOUNT)
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


async def test_a_search_returns_its_pages_with_a_summary_and_progress(
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
    summary = result.content[0].text
    assert "pie guide https://a.example/pie" in summary
    assert "cake tips https://b.example/cake" in summary
    assert progress == [1, 2]


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


async def test_a_call_naming_nothing_to_search_is_refused(google_search: str) -> None:
    result = await call(google_search, "scrape", {"queries": []}, LICENSE)

    assert result.is_error


def test_without_a_license_the_plugin_answers_nothing(google_search: str) -> None:
    refused = httpx2.post(google_search, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
