"""The fail-fast transport, hedges, one detail wave, concurrent sources, short links
by hand, the zip-code session, the tool's text and progress, and the #id lookups."""

from __future__ import annotations

import asyncio
import importlib
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from scrapling.parser import Adaptor

from proprietary.amazon import (
    AmazonScrapeInput,
    fetch,
    parsers,
    scrape_products,
    scraper,
)
from proprietary.amazon.fetch import FetchResult, LocationSession
from proprietary.amazon.tests._fake_http import answering, raw
from proprietary.scraping import lifecycle, sessions
from proprietary.scraping.http import TransportError

_FIXTURES = Path(__file__).parent / "fixtures"
_PAGE = "<html><body>page</body></html>"
_CAPTCHA = "<html><title>Robot Check</title>Enter the characters you see below</html>"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _input(*urls: str, **kwargs: Any) -> AmazonScrapeInput:
    return AmazonScrapeInput(
        categoryOrProductUrls=[{"url": url} for url in urls], **kwargs
    )


class _Exit:
    """A leased sticky exit as the hedges and location sessions see it."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.country = "us"

    def proxy_url(self) -> str:
        return f"http://{self.name}"


@pytest.fixture
def leases(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    """Fresh exits named hedge-1, hedge-2...; records each release and its burn."""
    released: list[tuple[str, bool]] = []
    count = 0

    def lease_exit(_prefix: str, _country: str | None = None) -> _Exit:
        nonlocal count
        count += 1
        return _Exit(f"hedge-{count}")

    def release_exit(exit: _Exit, *, burned: bool = False) -> None:
        released.append((exit.name, burned))

    monkeypatch.setattr(sessions, "lease_exit", lease_exit)
    monkeypatch.setattr(sessions, "release_exit", release_exit)
    return released


@pytest.fixture
def quick_hedges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "_HEDGE_AFTER_S", {})
    monkeypatch.setattr(fetch, "_DEFAULT_HEDGE_AFTER_S", 0.05)


# --- AZ-2 / AZ-10: one fail-fast request per attempt, bytes decoded once ---


async def test_each_attempt_is_one_fail_fast_request_and_blocks_rotate(monkeypatch):
    replies = [
        TransportError("Timeout", 28, 4000.0, "Connection timed out"),
        raw("https://www.amazon.com/dp/B1", _CAPTCHA),
        raw("https://www.amazon.com/dp/B1", _PAGE, cookies={"session-id": "s"}),
    ]

    async def reply(_url: str, _kwargs: dict[str, Any]):
        answer = replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    sent = answering(monkeypatch, reply)
    result = await fetch.fetch_page("https://www.amazon.com/dp/B1", stage="pdp")

    assert result is not None
    assert (result.status, result.html, result.cookies) == (
        200,
        _PAGE,
        {"session-id": "s"},
    )
    assert len(sent) == 3
    assert {kwargs["timeout"] for kwargs in sent} == {(4.0, 12.0)}
    assert [kwargs["attempt"] for kwargs in sent] == [1, 2, 3]
    assert {kwargs["stage"] for kwargs in sent} == {"pdp"}


def test_block_markers_are_read_from_the_raw_bytes():
    assert fetch.is_blocked(_CAPTCHA.encode(), 200)
    assert not fetch.is_blocked(_PAGE.encode(), 200)
    assert fetch.is_blocked(b"", 202)
    assert fetch.is_blocked(b"", 200, {"X-Amzn-Waf-Action": "challenge"})


async def test_a_slow_attempt_is_hedged_on_a_fresh_sticky_exit(
    monkeypatch, leases, quick_hedges
):
    async def reply(url: str, kwargs: dict[str, Any]):
        if kwargs["proxy"] is None:  # the primary, on the rotating gateway
            await asyncio.sleep(5)
        return raw(url, f"<html>{kwargs['proxy']}</html>")

    sent = answering(monkeypatch, reply)
    started = time.monotonic()
    result = await fetch.fetch_page("https://www.amazon.com/s?k=x", stage="search")

    assert time.monotonic() - started < 1
    assert result is not None and result.html == "<html>http://hedge-1</html>"
    assert [kwargs["proxy"] for kwargs in sent] == [None, "http://hedge-1"]
    assert leases == [("hedge-1", False)]


async def test_a_hedge_without_a_free_sticky_slot_goes_out_on_the_gateway(
    monkeypatch, quick_hedges
):
    def lease_exit(_prefix: str, _country: str | None = None) -> _Exit:
        raise RuntimeError("no free sticky exit slot")

    monkeypatch.setattr(sessions, "lease_exit", lease_exit)
    replies = 0

    async def reply(url: str, _kwargs: dict[str, Any]):
        nonlocal replies
        replies += 1
        if replies == 1:  # the primary
            await asyncio.sleep(5)
        return raw(url, f"<html>reply-{replies}</html>")

    sent = answering(monkeypatch, reply)
    monkeypatch.setattr(fetch, "get_geo_proxy_url", lambda country=None: "http://geo")
    started = time.monotonic()
    result = await fetch.fetch_page(
        "https://www.amazon.com/s?k=x", country="us", stage="search"
    )

    assert time.monotonic() - started < 1
    assert result is not None and result.html == "<html>reply-2</html>"
    assert [kwargs["proxy"] for kwargs in sent] == ["http://geo", "http://geo"]


async def test_a_call_starts_at_most_three_hedges(monkeypatch, leases, quick_hedges):
    async def reply(url: str, kwargs: dict[str, Any]):
        if kwargs["proxy"] is None:
            await asyncio.sleep(0.3)
        return raw(url, _PAGE)

    sent = answering(monkeypatch, reply)
    _notes, hedges, notes = fetch.start_call()
    try:
        await asyncio.gather(
            *(
                fetch.fetch_page(f"https://www.amazon.com/dp/B{n}", stage="seller")
                for n in range(5)
            )
        )
    finally:
        fetch.end_call(hedges, notes)

    assert sum(kwargs["proxy"] is not None for kwargs in sent) == 3


async def test_amazon_hedge_0_sends_one_request_per_attempt(
    monkeypatch, leases, quick_hedges
):
    monkeypatch.setenv("AMAZON_HEDGE", "0")

    async def reply(url: str, kwargs: dict[str, Any]):
        await asyncio.sleep(0.2)
        return raw(url, _PAGE)

    sent = answering(monkeypatch, reply)
    _notes, hedges, notes = fetch.start_call()
    try:
        await fetch.fetch_page("https://www.amazon.com/dp/B1", stage="seller")
    finally:
        fetch.end_call(hedges, notes)

    assert len(sent) == 1
    assert leases == []


async def test_a_pinned_proxy_is_never_hedged(monkeypatch, leases, quick_hedges):
    async def reply(url: str, _kwargs: dict[str, Any]):
        await asyncio.sleep(0.2)
        return raw(url, _PAGE)

    sent = answering(monkeypatch, reply)
    await fetch.fetch_page("https://www.amazon.com/", proxy="http://pinned")

    assert [kwargs["proxy"] for kwargs in sent] == ["http://pinned"]


# --- AZ-5: one detail wave; AZ-6: sources side by side, in order ---


async def test_a_search_loads_its_details_in_one_wave():
    running = peak = 0

    async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return [{"asin": card["asin"]}]

    cards = [{"asin": f"B{n}"} for n in range(12)]
    items = [item async for item in scraper._card_details(cards, 10, load_card)]

    assert [item["asin"] for item in items] == [f"B{n}" for n in range(10)]
    assert peak == 10  # was 8, then a second wave of 2


async def test_a_smaller_detail_wave_cap_splits_the_wave(monkeypatch):
    monkeypatch.setattr(scraper, "_DETAIL_WAVE_MAX", 8)
    running = peak = 0

    async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return [{"asin": card["asin"]}]

    cards = [{"asin": f"B{n}"} for n in range(12)]
    items = [item async for item in scraper._card_details(cards, 10, load_card)]

    assert len(items) == 10
    assert peak == 8


async def test_sources_run_side_by_side_and_keep_their_order(monkeypatch):
    delays = {"B0000000A1": 0.3, "B0000000A2": 0.2, "B0000000A3": 0.1}
    running = peak = 0

    async def fetch_page(url: str, **_kwargs: Any) -> FetchResult:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(delays[url.rsplit("/", 1)[1]])
        running -= 1
        return FetchResult(status=404, html="", url=url, cookies={})

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    urls = [f"https://www.amazon.com/dp/{asin}" for asin in delays]
    items = await scrape_products(_input(*urls))

    assert [item["input"] for item in items] == urls
    assert peak == 3


async def test_flows_report_their_stages(monkeypatch):
    async def fetch_page(url: str, **_kwargs: Any) -> FetchResult:
        return FetchResult(
            status=200, html=_fixture("search.html"), url=url, cookies={}
        )

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    stages: list[str] = []

    async def heard(message: str) -> None:
        stages.append(message)

    await scrape_products(
        _input(
            "https://www.amazon.com/s?k=headphones",
            maxItemsPerStartUrl=2,
            scrapeProductDetails=False,
        ),
        on_stage=heard,
    )

    assert stages[0] == "fetching search page 1"


# --- AZ-8: short links resolved by hand ---


async def test_a_short_link_is_followed_by_hand_up_to_the_amazon_page(monkeypatch):
    hops = {
        "https://a.co/d/abc": "https://amzn.to/xyz",
        "https://amzn.to/xyz": "https://www.amazon.com/dp/B09V3KXJPB?ref=share",
    }

    async def reply(url: str, _kwargs: dict[str, Any]):
        return raw(url, status=302, headers={"Location": hops[url]})

    sent = answering(monkeypatch, reply)
    target = await fetch.resolve_shortlink("https://a.co/d/abc")

    # The product page itself is left to the product flow: fetched once, not twice.
    assert target == "https://www.amazon.com/dp/B09V3KXJPB?ref=share"
    assert [kwargs["url"] for kwargs in sent] == list(hops)
    assert {kwargs["allow_redirects"] for kwargs in sent} == {False}


async def test_a_short_link_that_never_reaches_amazon_resolves_to_nothing(monkeypatch):
    async def reply(url: str, _kwargs: dict[str, Any]):
        return raw(url, status=302, headers={"Location": url + "x"})

    sent = answering(monkeypatch, reply)

    assert await fetch.resolve_shortlink("https://a.co/d/abc") is None
    assert len(sent) == fetch._SHORTLINK_HOPS


# --- AZ-9: the zip-code session ---


def test_the_location_token_is_read_from_the_escaped_modal_json():
    page = (
        '<span id="nav-global-location-data-modal-action" data-a-modal="{&quot;'
        "ajaxHeaders&quot;:{&quot;anti-csrftoken-a2z&quot;:&quot;tok-123&quot;}}"
        '"></span>'
    )

    assert fetch._csrf_token(page) == "tok-123"
    assert fetch._csrf_token("CSRF_TOKEN : 'tok-456',") == "tok-456"


@pytest.fixture
def no_locations():
    fetch._location_sessions.clear()
    fetch._location_failures.clear()
    yield
    fetch._location_sessions.clear()
    fetch._location_failures.clear()


async def test_a_failed_zip_is_reported_and_not_retried_for_a_while(
    monkeypatch, no_locations
):
    homes = 0

    async def mint(_key, **_kwargs):
        nonlocal homes
        homes += 1
        return None, "Amazon's home page had no location token"

    async def fetch_page(url: str, **_kwargs: Any) -> FetchResult:
        return FetchResult(
            status=200, html=_fixture("search.html"), url=url, cookies={}
        )

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    request = _input(
        "https://www.amazon.com/s?k=headphones",
        maxItemsPerStartUrl=1,
        scrapeProductDetails=False,
        zipCode="10001",
        countryCode="US",
    )
    first: list[str] = []
    second: list[str] = []
    items = await scrape_products(request, notes=first)
    await scrape_products(request, notes=second)

    assert items[0]["asin"] == "B09V3KXJPB"
    assert homes == 1
    expected = [
        "zip_code 10001 was not applied: Amazon's home page had no location token"
    ]
    assert first == second == expected


async def test_a_refused_location_exit_mints_a_new_session(monkeypatch, no_locations):
    key = ("www.amazon.com", "10001", "US")
    refused = LocationSession(
        proxy="http://zip-1",
        cookies={"session-id": "old"},
        country_code="US",
        zip_code="10001",
        location_text="10001",
        created_at=time.time(),
        key=key,
    )
    fetch._location_sessions[key] = refused
    fresh = LocationSession(
        proxy="http://zip-2",
        cookies={"session-id": "new"},
        country_code="US",
        zip_code="10001",
        location_text="10001",
        created_at=time.time(),
        key=key,
    )

    async def mint(_key, **_kwargs):
        return fresh, ""

    async def reply(url: str, kwargs: dict[str, Any]):
        return raw(url, _CAPTCHA if kwargs["proxy"] == "http://zip-1" else _PAGE)

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    sent = answering(monkeypatch, reply)
    result = await fetch.fetch_page("https://www.amazon.com/s?k=x", location=refused)

    assert result is not None and result.html == _PAGE
    assert [(kwargs["proxy"], kwargs["cookies"]) for kwargs in sent] == [
        ("http://zip-1", {"session-id": "old"}),
        ("http://zip-2", {"session-id": "new"}),
    ]
    assert fetch._location_sessions[key] is fresh


async def test_a_location_exit_serves_three_requests_at_a_time(monkeypatch):
    session = LocationSession(
        proxy="http://zip-1",
        cookies={},
        country_code="US",
        zip_code="10001",
        location_text="10001",
        created_at=time.time(),
    )
    running = peak = 0

    async def reply(url: str, _kwargs: dict[str, Any]):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return raw(url, _PAGE)

    answering(monkeypatch, reply)
    await asyncio.gather(
        *(
            fetch.fetch_page(f"https://www.amazon.com/dp/B{n}", location=session)
            for n in range(7)
        )
    )

    assert peak == 3


# --- SW-6 / SW-8: the tool's lifespan and what the agent reads ---


@pytest.fixture
def server_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", "test-account")
    return importlib.import_module("proprietary.amazon.server")


async def test_the_plugin_lifespan_holds_the_shared_pools(server_module):
    closed: list[str] = []

    async def close() -> None:
        closed.append("pools")

    async with server_module.lifespan():
        lifecycle.at_shutdown(close)

    assert closed == ["pools"]


def test_the_text_shows_what_an_agent_answers_from(server_module):
    product = {
        "title": "Mouse",
        "asin": "B1",
        "url": "https://www.amazon.com/Mouse/dp/B1/ref=sr_1_3?dib=tracking",
        "price": {"value": 29.99, "currency": "USD"},
        "listPrice": {"value": 49.99, "currency": "USD"},
        "stars": 4.5,
        "reviewsCount": 1200,
        "description": "A mouse.",
        "features": ["one", "two"],
        "productPageReviews": [{"stars": 5.0, "title": "Great", "text": "Works."}],
        "offers": [
            {
                "price": {"value": 28.0, "currency": "USD"},
                "condition": "New",
                "seller": {"name": "Shop", "averageRating": 4.8},
            }
        ],
        "highResolutionImages": ["https://m.media-amazon.com/1.jpg"],
        "categoryPageData": {"position": 3},
    }
    error = {
        "error": "product_not_found",
        "errorDescription": "The product page was not found.",
        "input": "https://www.amazon.com/dp/B2",
    }

    result = server_module.tool_result(
        server_module._summary([product, error], ["zip_code 1 was not applied: x"]),
        [product, error],
        project=server_module._projected,
    )
    header, note, first, second = result.content[0].text.split("\n")

    assert header == "1 Amazon products, 1 errors"
    assert note == "zip_code 1 was not applied: x"
    shown = json.loads(first)
    assert shown["url"] == "https://www.amazon.com/dp/B1"
    assert shown["price"] == "29.99 USD"
    assert shown["listPrice"] == "49.99 USD"
    assert shown["reviews"] == [{"stars": 5.0, "title": "Great", "text": "Works."}]
    assert shown["offers"][0]["seller"] == {"name": "Shop", "rating": 4.8}
    assert shown["searchPosition"] == 3
    assert "highResolutionImages" not in shown
    assert json.loads(second)["error"] == "product_not_found"
    assert result.structured_content == {"items": [product, error]}


# --- AZ-11 (first step): #id lookups from the ID table, same output ---


@pytest.mark.parametrize(
    "page", ["product.html", "product_full_real.html", "product_fallback_real.html"]
)
def test_id_lookups_parse_the_page_exactly_as_the_css_scan(monkeypatch, page):
    html = _fixture(page)
    kwargs = {
        "asin": "B07CMS5Q6P",
        "url": "https://www.amazon.com/dp/B07CMS5Q6P",
        "domain": "www.amazon.com",
    }
    fast = parsers.parse_product(html, **kwargs)
    monkeypatch.setattr(parsers, "_ID_SELECTOR_RE", re.compile(r"(?!)"))

    assert parsers.parse_product(html, **kwargs) == fast


def test_an_id_lookup_takes_the_first_element_with_that_id():
    doc = Adaptor(
        '<div id="title"><span>first</span></div><div id="title">second</div>'
        '<p class="x"><b id="inner">inner</b></p>'
    )
    paragraph = parsers._one(doc, ".x")

    assert parsers._text(parsers._one(doc, "#title")) == "first"
    assert parsers._text(parsers._one(paragraph, "#inner")) == "inner"
    assert parsers._one(doc, "#missing") is None
