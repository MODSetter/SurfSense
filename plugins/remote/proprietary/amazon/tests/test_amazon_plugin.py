"""The Amazon plugin as the app reaches it: its MCP server on the host, behind the license.

Amazon itself is faked at the scraper's network seam, the shared `http.request`, and
its proxy URLs; the host, the license check, the tool and Amazon's parsing are real.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.amazon.tests._fake_http import answering, raw
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)

LICENSE = {"Authorization": "License k-1"}
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def amazon(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Amazon plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"amazon"})) as base:
            yield f"{base}/amazon/mcp"


def amazon_answering(
    monkeypatch: pytest.MonkeyPatch, answer: dict[str, str], default: str = ""
) -> list[str]:
    """Amazon serving the fixture named for the first URL fragment it matches."""
    asked: list[str] = []

    async def reply(url: str, _kwargs: dict[str, Any]) -> Any:
        asked.append(url)
        name = next((answer[key] for key in answer if key in url), default)
        html = (FIXTURES / name).read_text(encoding="utf-8") if name else ""
        return raw(url, html)

    answering(monkeypatch, reply)
    return asked


async def test_it_offers_one_read_only_tool_that_reaches_the_web(amazon: str) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(amazon, http_client=http)) as client,
    ):
        (tool,) = (await client.list_tools()).tools

    assert tool.name == "scrape"
    assert tool.annotations is not None
    assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (
        True,
        True,
    )


async def test_a_search_returns_its_products_with_a_summary_and_progress(
    amazon: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = amazon_answering(monkeypatch, {"page=1": "search.html"})
    progress: list[float] = []

    result = await call(
        amazon,
        "scrape",
        {"search_terms": ["headphones"], "max_items": 2, "include_details": False},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["asin"] for item in items] == ["B09V3KXJPB", "B09V3KXJP1"]
    assert result.content[0].text.startswith("2 Amazon products, 0 errors")
    assert progress[-1] == 2
    assert asked[0] == "https://www.amazon.com/s?k=headphones&page=1"


async def test_a_product_url_returns_its_details(
    amazon: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    amazon_answering(monkeypatch, {"/dp/": "product.html"})

    result = await call(
        amazon, "scrape", {"urls": ["https://www.amazon.com/dp/B09V3KXJPB"]}, LICENSE
    )

    (item,) = result.structured_content["items"]
    assert item["title"] == "Example Wireless Headphones"
    assert item["price"] == {"value": 49.99, "currency": "USD"}
    # The text carries each item as a JSON line (SW-8), not a title list, so an
    # agent that reads only the text still sees the price.
    header, line = result.content[0].text.split("\n")
    assert header == "1 Amazon products, 0 errors"
    shown = json.loads(line)
    assert (shown["title"], shown["asin"], shown["price"]) == (
        "Example Wireless Headphones",
        "B09V3KXJPB",
        "49.99 USD",
    )


async def test_amazon_blocking_every_exit_reads_as_an_error_item(
    amazon: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As the scraper API answered: one input's failure is an item, not the call's."""
    asked = amazon_answering(monkeypatch, {}, default="blocked.html")

    result = await call(
        amazon, "scrape", {"urls": ["https://www.amazon.com/dp/B09V3KXJPB"]}, LICENSE
    )

    assert not result.is_error
    (item,) = result.structured_content["items"]
    assert item["error"] == "product_not_found"
    assert result.content[0].text.startswith("0 Amazon products, 1 errors")
    assert len(asked) == 8


async def test_a_call_naming_nothing_to_scrape_is_refused(amazon: str) -> None:
    result = await call(amazon, "scrape", {}, LICENSE)

    assert result.is_error
    assert "urls" in result.content[0].text


async def test_a_url_that_is_not_http_is_refused(amazon: str) -> None:
    result = await call(
        amazon, "scrape", {"urls": ["amazon.com/dp/B09V3KXJPB"]}, LICENSE
    )

    assert result.is_error
    assert "Not an http(s) URL" in result.content[0].text


async def test_more_than_twenty_sources_together_are_refused(amazon: str) -> None:
    arguments = {
        "urls": [f"https://www.amazon.com/dp/B09V3KXJP{n}" for n in range(10)],
        "search_terms": [f"term {n}" for n in range(11)],
    }

    result = await call(amazon, "scrape", arguments, LICENSE)

    assert result.is_error
    assert "no more than 20" in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(amazon: str) -> None:
    refused = httpx2.post(amazon, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
