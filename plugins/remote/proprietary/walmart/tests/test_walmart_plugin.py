"""The Walmart plugin as the app reaches it: its MCP server on the host, behind the license.

Walmart itself is faked at the scraper's network seam, Scrapling's `AsyncFetcher`,
with no proxy; the host, the license check, the tools and Walmart's parsing are real.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.license_check import keygen
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen
from proprietary.walmart import fetch

LICENSE = {"Authorization": "License k-1"}

# Read once, so the fake Walmart never touches the disk inside the event loop.
PAGES = {
    name: (Path(__file__).parent / "fixtures" / f"{name}.html").read_text("utf-8")
    for name in ("product", "listing", "reviews", "blocked")
} | {"empty": "<html></html>"}


@pytest.fixture
def walmart(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Walmart plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setattr(keygen, "KEYGEN_API_URL", keygen_url)
        monkeypatch.setattr(keygen, "SURFSENSE_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"walmart"})) as base:
            yield f"{base}/walmart/mcp"


@dataclass
class Page:
    """A Scrapling response, as far as `fetch_page` reads one."""

    url: str
    html_content: str
    status: int = 200
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


def walmart_answering(
    monkeypatch: pytest.MonkeyPatch, page_for: Callable[[str], str]
) -> list[str]:
    """Walmart serving `page_for(url)` for every URL asked; keeps each URL asked for."""
    asked: list[str] = []

    class Fetcher:
        @staticmethod
        async def get(url: str, **_: Any) -> Page:
            asked.append(url)
            return Page(url=url, html_content=PAGES[page_for(url)])

    monkeypatch.setattr(fetch, "AsyncFetcher", Fetcher)
    monkeypatch.setattr(fetch, "get_geo_proxy_url", lambda country=None: None)
    monkeypatch.setattr(fetch, "get_sticky_proxy_url", lambda *_, **__: None)
    return asked


def first_page_only(name: str) -> Callable[[str], str]:
    """The page `name` on page 1; an empty listing after, so pagination stops."""
    return lambda url: name if "page=1" in url else "empty"


async def test_it_offers_two_read_only_tools_that_reach_the_web(walmart: str) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(walmart, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert sorted(tool.name for tool in tools) == ["reviews", "scrape"]
    for tool in tools:
        assert tool.annotations is not None
        assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (
            True,
            True,
        )


async def test_a_search_returns_its_products_with_a_summary_and_progress(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = walmart_answering(monkeypatch, first_page_only("listing"))
    progress: list[float] = []

    result = await call(
        walmart,
        "scrape",
        {"search_terms": ["laptop"], "max_items": 2, "include_details": False},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["usItemId"] for item in items] == ["791595618", "999001"]
    assert result.content[0].text.startswith("2 Walmart products")
    assert progress[-1] == 2
    assert asked == ["https://www.walmart.com/search?q=laptop&page=1"]


async def test_a_product_url_returns_its_details(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    walmart_answering(monkeypatch, lambda url: "product")

    result = await call(
        walmart,
        "scrape",
        {"urls": [" https://www.walmart.com/ip/Midea-AC/212092810 "]},
        LICENSE,
    )

    assert not result.is_error
    (item,) = result.structured_content["items"]
    assert item["name"].startswith("Midea")
    assert item["price"] == {"value": 149.0, "currency": "USD"}
    assert "Midea 5,000 BTU" in result.content[0].text


async def test_reviews_return_each_review_with_a_summary_and_progress(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = walmart_answering(monkeypatch, first_page_only("reviews"))
    progress: list[float] = []

    result = await call(
        walmart,
        "reviews",
        {"item_ids": ["212092810"], "sort_by": "most-helpful"},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["reviewId"] for item in items] == ["296013686", "296013687"]
    assert all(item["usItemId"] == "212092810" for item in items)
    assert result.content[0].text.startswith("2 Walmart reviews")
    assert progress[-1] == 2
    assert "sort=helpful" in asked[0]


async def test_walmart_blocking_every_exit_reads_as_a_failed_input(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As in the backend, a block is an error item in the result, not a failed call."""
    asked = walmart_answering(monkeypatch, lambda url: "blocked")

    result = await call(
        walmart, "scrape", {"urls": ["https://www.walmart.com/ip/212092810"]}, LICENSE
    )

    assert not result.is_error
    (item,) = result.structured_content["items"]
    assert item["error"] == "product_not_found"
    assert result.content[0].text.startswith("0 Walmart products, 1 failed")
    assert len(asked) == 6


@pytest.mark.parametrize(
    ("tool", "arguments", "said"),
    [
        ("scrape", {}, "urls or search_terms"),
        ("scrape", {"urls": ["walmart.com/ip/1"]}, "Not an http(s) URL"),
        ("scrape", {"urls": ["https://w/ip/1"] * 11, "search_terms": ["t"] * 10}, "20"),
        ("reviews", {}, "urls or item_ids"),
        ("reviews", {"item_ids": ["1"], "max_reviews": 5001}, "max_reviews"),
    ],
)
async def test_a_call_asking_for_nothing_valid_is_refused(
    walmart: str, tool: str, arguments: dict[str, Any], said: str
) -> None:
    result = await call(walmart, tool, arguments, LICENSE)

    assert result.is_error
    assert said in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(walmart: str) -> None:
    refused = httpx2.post(walmart, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
