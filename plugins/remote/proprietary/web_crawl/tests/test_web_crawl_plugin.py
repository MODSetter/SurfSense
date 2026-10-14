"""The Web Crawl plugin as the app reaches it: its MCP server on the host, behind the license.

The web is faked at the static tier's fetcher, `AsyncFetcher`, and DNS at the
destination guard's resolver: the guard refuses loopback, so a site served on
loopback could not be crawled. The host, the license check, the tool, the
extraction and the spider are real.
"""

from collections.abc import Iterator

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)
from proprietary.web_crawl import connector, net_guard

LICENSE = {"Authorization": "License k-1"}

PARAGRAPH = "Sourdough needs a lively starter, a long rise and a hot oven. " * 12


def page(title: str, body: str) -> str:
    return (
        f"<html><head><title>{title}</title></head><body>"
        f"<article><h1>{title}</h1><p>{body}</p></article></body></html>"
    )


SITE = {
    "https://bread.example/": page(
        "Bread at home",
        PARAGRAPH
        + '<a href="/starter">Starter</a> <a href="/oven">Oven</a>'
        + ' <a href="https://elsewhere.example/">Elsewhere</a>',
    ),
    "https://bread.example/starter": page(
        "Keeping a starter", "Feed the starter twice a day. " * 20
    ),
    "https://bread.example/oven": page("Oven heat", "Preheat to 250 C. " * 30),
}


@pytest.fixture
def web_crawl(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Web Crawl plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"web-crawl"})) as base:
            yield f"{base}/web-crawl/mcp"


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """`SITE` answering the static tier, every name resolving public; keeps each URL fetched."""
    fetched: list[str] = []

    class Page:
        def __init__(self, html: str | None) -> None:
            self.status = 200 if html else 404
            self.html_content = html or ""

    class AsyncFetcher:
        @staticmethod
        async def get(url: str, **_kwargs) -> Page:
            fetched.append(url)
            return Page(SITE.get(url))

    async def no_browser(*_args, **_kwargs) -> None:
        raise NotImplementedError("no browser in tests")

    monkeypatch.setattr(connector, "AsyncFetcher", AsyncFetcher)
    monkeypatch.setattr(
        connector.WebCrawlerConnector, "_crawl_with_dynamic", no_browser
    )
    monkeypatch.setattr(
        connector.WebCrawlerConnector, "_crawl_with_stealthy", no_browser
    )
    monkeypatch.setattr(net_guard, "_resolve_host", lambda _host: ["93.184.216.34"])
    return fetched


async def test_it_offers_one_read_only_tool_that_reaches_the_web(
    web_crawl: str,
) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(web_crawl, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert [tool.name for tool in tools] == ["crawl"]
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True
    assert tools[0].annotations.open_world_hint is True


async def test_one_page_is_read_with_its_text_in_the_summary(
    web_crawl: str, web: list[str]
) -> None:
    progress: list[float] = []

    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"]},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["url"] for item in items] == ["https://bread.example/"]
    assert items[0]["status"] == "success"
    assert "lively starter" in items[0]["markdown"]
    summary = result.content[0].text
    assert "Bread at home" in summary
    assert "https://bread.example/" in summary
    assert "lively starter" in summary
    assert progress == [1]
    assert web == ["https://bread.example/"]


async def test_a_depth_one_crawl_follows_the_site_s_links_only(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"], "max_crawl_depth": 1},
        LICENSE,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert {item["url"] for item in items} == set(SITE)
    followed = {item["url"]: item["crawl"] for item in items}
    assert followed["https://bread.example/oven"]["depth"] == 1
    assert (
        followed["https://bread.example/oven"]["referrerUrl"]
        == "https://bread.example/"
    )
    assert "https://elsewhere.example/" not in web
    summary = result.content[0].text
    assert "Keeping a starter https://bread.example/starter" in summary
    # Several pages: their text is in the structured result, not the summary.
    assert "Feed the starter" not in summary


async def test_max_length_cuts_each_page_s_text(web_crawl: str, web: list[str]) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"], "max_length": 40},
        LICENSE,
    )

    assert len(result.structured_content["items"][0]["markdown"]) == 40


async def test_a_loopback_address_is_refused_unfetched(
    web_crawl: str, web: list[str]
) -> None:
    """The host's own network is no page to read."""
    result = await call(
        web_crawl, "crawl", {"start_urls": ["http://127.0.0.1:8000/"]}, LICENSE
    )

    assert result.is_error
    assert "not publicly routable" in result.content[0].text
    assert web == []


async def test_a_url_that_is_not_http_is_refused(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl, "crawl", {"start_urls": ["file:///etc/passwd"]}, LICENSE
    )

    assert result.is_error
    assert "file:///etc/passwd" in result.content[0].text
    assert web == []


async def test_a_pattern_that_is_not_a_regex_is_refused(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {
            "start_urls": ["https://bread.example/"],
            "max_crawl_depth": 1,
            "include_url_patterns": ["(unclosed"],
        },
        LICENSE,
    )

    assert result.is_error
    assert "(unclosed" in result.content[0].text
    assert web == []


async def test_a_call_naming_nothing_to_read_is_refused(web_crawl: str) -> None:
    result = await call(web_crawl, "crawl", {"start_urls": []}, LICENSE)

    assert result.is_error


def test_without_a_license_the_plugin_answers_nothing(web_crawl: str) -> None:
    refused = httpx2.post(web_crawl, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
