"""The Walmart plugin as the app reaches it: its MCP server on the host, behind the license.

Walmart itself is faked at the scraper's network seam, the shared transport's
`http.request`, with no proxy; the host, the license check, the tools, the retry
policy and Walmart's parsing are real.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

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
from proprietary.walmart.tests.fake_http import answering, raw

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
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"walmart"})) as base:
            yield f"{base}/walmart/mcp"


def walmart_answering(
    monkeypatch: pytest.MonkeyPatch, page_for: Callable[[str], str]
) -> list[str]:
    """Walmart serving `page_for(url)` for every URL asked; keeps each URL asked for."""
    return answering(monkeypatch, lambda url: raw(url, PAGES[page_for(url)]))


def lines(text: str) -> list[dict[str, Any]]:
    """The items as the agent reads them: one JSON line each, after the summary."""
    return [json.loads(line) for line in text.splitlines()[1:]]


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
    assert [line["text"] for line in lines(result.content[0].text)] == [
        item["text"] for item in items
    ]
    # One product: its id would only repeat on every line.
    assert all("usItemId" not in line for line in lines(result.content[0].text))
    # Progress now goes through the shared limiter (one notice a second), so a
    # call this fast reports its first stage; the values still only rise.
    assert progress and progress == sorted(progress)
    assert "sort=helpful" in asked[0]


async def test_reviews_of_several_products_are_counted_per_product(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A text cut short still says whose reviews it holds and whose it lacks."""
    walmart_answering(monkeypatch, first_page_only("reviews"))

    result = await call(
        walmart, "reviews", {"item_ids": ["212092810", "791595618"]}, LICENSE, []
    )

    text = result.content[0].text
    assert text.splitlines()[0] == (
        "4 Walmart reviews (2 for 212092810, 2 for 791595618)"
    )
    assert [line["usItemId"] for line in lines(text)] == [
        "212092810",
        "212092810",
        "791595618",
        "791595618",
    ]


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
    # Four exits now (was six): with each try capped at 16 s, the page's budget
    # is 25 s rather than minutes.
    assert len(asked) == 4


async def test_a_search_keeps_a_blocked_products_card_and_says_so(
    walmart: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def page_for(url: str) -> str:
        if "791595618" in url:
            return "blocked"
        return "product" if "/ip/" in url else first_page_only("listing")(url)

    asked = walmart_answering(monkeypatch, page_for)

    result = await call(
        walmart, "scrape", {"search_terms": ["laptop"], "max_items": 2}, LICENSE
    )

    assert not result.is_error
    card, detailed = result.structured_content["items"]
    assert card["usItemId"] == "791595618"
    assert card["detailsError"].startswith("product_not_found")
    assert "longDescription" in detailed
    # The items are now in the text as JSON lines (opencode reads only the
    # text), so the card's price and its failed details are read from there.
    text = result.content[0].text
    assert text.startswith("2 Walmart products; 1 listing card only (details failed)")
    card_line, detailed_line = lines(text)
    assert card_line["name"].startswith("Restored Acer Chromebook")
    assert card_line["price"] == 79.99
    assert card_line["detailsError"].startswith("product_not_found")
    assert "longDescription" in detailed_line
    assert not any("page=2" in url for url in asked)


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


@pytest.fixture
def walmart_server(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The plugin's server module, importable without a Keygen account in the env."""
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    from proprietary.walmart import server

    return server


def test_the_text_keeps_what_an_agent_compares_and_leaves_out_the_bulk(
    walmart_server: Any,
) -> None:
    _product_fields = walmart_server._product_fields
    _review_fields = walmart_server._review_fields

    product = {
        "usItemId": "1",
        "name": "Soap",
        "price": {"value": 3.5, "currency": "USD"},
        "stars": 4.6,
        "images": ["https://i5.walmartimages.com/a.jpg"],
        "variants": [{"id": "size"}],
        "fulfillment": {"shipping": {"deliveryDate": "2026-10-16", "location": "x"}},
        "reviewsSample": {
            "topReviews": [{"rating": 5, "title": "Good", "text": "y" * 500}] * 5
        },
    }
    projected = _product_fields(product)

    assert (projected["price"], projected["currency"], projected["stars"]) == (
        3.5,
        "USD",
        4.6,
    )
    assert "images" not in projected and "variants" not in projected
    assert projected["fulfillment"]["shipping"]["deliveryDate"] == "2026-10-16"
    assert len(projected["topReviews"]) == 2
    assert len(projected["topReviews"][0]["text"]) == 201

    same = {"usItemId": "1", "text": "ok", "reviewedItemId": "1"}
    other = {**same, "reviewedItemId": "2", "reviewedItemName": "Soap, 2 pack"}
    assert _review_fields(same)["reviewedItemId"] is None
    assert _review_fields(other)["reviewedItemName"] == "Soap, 2 pack"


def test_ten_detailed_products_fit_the_text_with_room_to_spare(
    walmart_server: Any,
) -> None:
    """Descriptions and specifications are cut, so the default ten all show."""
    product = {
        "usItemId": "1",
        "name": "Soap",
        "shortDescription": "s" * 600,
        "longDescription": "l" * 2000,
        "specifications": {f"spec {n}": "value" * 4 for n in range(40)},
    }

    projected = walmart_server._product_fields(product)

    assert len(projected["shortDescription"]) == len(projected["longDescription"])
    assert len(projected["longDescription"]) == 301
    assert list(projected["specifications"]) == [f"spec {n}" for n in range(15)]


def test_a_review_line_carries_no_padding(walmart_server: Any) -> None:
    review = {
        "usItemId": "1",
        "rating": 5.0,
        "text": "ok",
        "verifiedPurchase": True,
        "positiveFeedback": 0,
    }

    line = walmart_server._review_fields(review, with_id=False)

    assert line["rating"] == 5 and isinstance(line["rating"], int)
    assert line["usItemId"] is None and line["helpful"] is None
    assert line["verified"] is True
    assert walmart_server._review_fields({**review, "rating": 4.5})["rating"] == 4.5


async def test_its_lifespan_joins_the_shared_shutdown(
    monkeypatch: pytest.MonkeyPatch, walmart_server: Any
) -> None:
    from proprietary.scraping import lifecycle

    entered: list[str] = []
    real = lifecycle.lifespan

    def lifespan():
        entered.append("walmart")
        return real()

    monkeypatch.setattr(lifecycle, "lifespan", lifespan)
    async with walmart_server.lifespan():
        pass

    assert entered == ["walmart"]
