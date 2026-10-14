"""Zip sessions that give their exits back and label items honestly, short links
through Amazon redirectors, non-English fallback pages and ratings, the settings,
progress and text an agent sees."""

from __future__ import annotations

import asyncio
import importlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from proprietary.amazon import AmazonScrapeInput, fetch, scrape_products, scraper
from proprietary.amazon.fetch import FetchResult, LocationSession
from proprietary.amazon.parsers import (
    FALLBACK_PDP_MARKER,
    is_fallback_product_page,
    parse_search_page,
)
from proprietary.amazon.tests._fake_http import answering, raw
from proprietary.scraping import sessions
from proprietary.scraping.http import TransportError

_FIXTURES = Path(__file__).parent / "fixtures"
_PAGE = "<html><body>page</body></html>"
_KEY = ("www.amazon.com", "10001", "US")


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _input(url: str, **kwargs: Any) -> AmazonScrapeInput:
    return AmazonScrapeInput(categoryOrProductUrls=[{"url": url}], **kwargs)


class _Exit:
    def __init__(self, name: str) -> None:
        self.name = name
        self.country = "us"

    def proxy_url(self) -> str:
        return f"http://{self.name}"


def _session(name: str, *, age_s: float = 0.0, exit: Any = None) -> LocationSession:
    return LocationSession(
        proxy=f"http://{name}",
        cookies={"session-id": name},
        country_code="US",
        zip_code="10001",
        location_text="10001",
        created_at=time.time() - age_s,
        exit=exit,
        key=_KEY,
    )


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    gone: list[tuple[str, bool]] = []

    def release_exit(exit: _Exit, *, burned: bool = False) -> None:
        gone.append((exit.name, burned))

    monkeypatch.setattr(sessions, "release_exit", release_exit)
    return gone


@pytest.fixture(autouse=True)
def no_locations():
    fetch._location_sessions.clear()
    fetch._location_failures.clear()
    yield
    fetch._location_sessions.clear()
    fetch._location_failures.clear()


# --- the zip session's sticky exit ---


async def test_an_expired_location_session_gives_its_exit_back(monkeypatch, released):
    fetch._location_sessions[_KEY] = _session(
        "zip-old", age_s=fetch._LOCATION_SESSION_TTL_S + 1, exit=_Exit("zip-old")
    )
    fresh = _session("zip-new")

    async def mint(_key, **_kwargs):
        return fresh, ""

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    session = await fetch.get_location_session(
        "www.amazon.com", zip_code="10001", country_code="US"
    )

    assert session is fresh
    assert released == [("zip-old", False)]  # free again, not quarantined


async def test_a_location_session_minted_without_a_free_slot_stays_on_the_proxy(
    monkeypatch,
):
    proxies: list[str | None] = []

    async def fetch_page(url: str, *, proxy: str | None = None, **_kwargs):
        proxies.append(proxy)
        html = (
            '<input name="anti-csrftoken-a2z" value="tok">' if not proxies[1:] else ""
        )
        return FetchResult(status=200, html=html, url=url, cookies={})

    monkeypatch.setattr(fetch, "_lease_location_exit", lambda _country: None)
    monkeypatch.setattr(fetch, "get_geo_proxy_url", lambda country=None: "http://geo")
    monkeypatch.setattr(fetch, "fetch_page", fetch_page)
    session, _reason = await fetch._mint_location_session(_KEY, country="us")

    assert session is not None and session.proxy == "http://geo"
    assert proxies == ["http://geo", "http://geo"]


async def test_one_failed_handshake_retries_the_same_location_exit(monkeypatch):
    session = _session("zip-1")
    fetch._location_sessions[_KEY] = session
    failures = [TransportError("TLS", 35, 900.0, "handshake failed")]

    async def reply(url: str, _kwargs: dict[str, Any]):
        if failures:
            raise failures.pop()
        return raw(url, _PAGE)

    async def mint(_key, **_kwargs):
        raise AssertionError("a healthy session was renewed")

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    sent = answering(monkeypatch, reply)
    result = await fetch.fetch_page("https://www.amazon.com/dp/B1", location=session)

    assert result is not None and result.location is session
    assert [kwargs["proxy"] for kwargs in sent] == ["http://zip-1", "http://zip-1"]


async def test_a_dead_location_exit_is_renewed_after_two_failures_in_a_row(
    monkeypatch, released
):
    session = _session("zip-1", exit=_Exit("zip-1"))
    fetch._location_sessions[_KEY] = session
    fresh = _session("zip-2")

    async def reply(url: str, kwargs: dict[str, Any]):
        if kwargs["proxy"] == "http://zip-1":
            raise TransportError("Timeout", 28, 4000.0, "Connection timed out")
        return raw(url, _PAGE)

    async def mint(_key, **_kwargs):
        return fresh, ""

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    sent = answering(monkeypatch, reply)
    result = await fetch.fetch_page("https://www.amazon.com/dp/B1", location=session)

    assert result is not None and result.location is fresh
    assert [kwargs["proxy"] for kwargs in sent] == [
        "http://zip-1",
        "http://zip-1",
        "http://zip-2",
    ]
    assert released == [("zip-1", True)]


async def test_a_task_holding_a_renewed_session_moves_to_the_new_one(monkeypatch):
    refused = _session("zip-1")
    fresh = _session("zip-2")
    fetch._location_sessions[_KEY] = fresh  # another task renewed it already

    async def reply(url: str, _kwargs: dict[str, Any]):
        return raw(url, _PAGE)

    sent = answering(monkeypatch, reply)
    result = await fetch.fetch_page("https://www.amazon.com/dp/B1", location=refused)

    assert result is not None and result.location is fresh
    assert [(kwargs["proxy"], kwargs["cookies"]) for kwargs in sent] == [
        ("http://zip-2", {"session-id": "zip-2"})
    ]


async def test_a_failed_renewal_leaves_the_page_without_the_zip(monkeypatch, released):
    session = _session("zip-1", exit=_Exit("zip-1"))
    fetch._location_sessions[_KEY] = session

    async def reply(url: str, kwargs: dict[str, Any]):
        if kwargs["proxy"] == "http://zip-1":
            return raw(url, "<title>Robot Check</title>")
        return raw(url, _PAGE)

    async def mint(_key, **_kwargs):
        return None, "the home page was blocked on every exit tried"

    monkeypatch.setattr(fetch, "_mint_location_session", mint)
    sent = answering(monkeypatch, reply)
    notes, hedges, notes_token = fetch.start_call()
    try:
        result = await fetch.fetch_page(
            "https://www.amazon.com/dp/B1", location=session
        )
    finally:
        fetch.end_call(hedges, notes_token)

    assert result is not None and result.html == _PAGE
    assert result.location is None
    assert "session-id" not in sent[-1]["cookies"]
    assert notes == [
        "zip_code 10001 was not applied: the home page was blocked on every exit tried"
    ]


@pytest.mark.parametrize("applied", [True, False])
async def test_a_product_is_labelled_with_the_location_its_page_came_from(
    monkeypatch, applied
):
    session = _session("zip-1")

    async def get_location_session(*_args, **_kwargs):
        return session

    async def fetch_page(url: str, **_kwargs):
        return FetchResult(
            status=200,
            html=_fixture("product.html"),
            url=url,
            cookies={},
            location=session if applied else None,
        )

    monkeypatch.setattr(scraper, "get_location_session", get_location_session)
    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        _input(
            "https://www.amazon.com/dp/B07CMS5Q6P",
            zipCode="10001",
            countryCode="US",
            maxOffers=0,
        )
    )

    assert items[0]["locationText"] == ("10001" if applied else None)
    assert items[0]["loadedCountryCode"] == ("US" if applied else None)


# --- short links ---


async def test_a_short_link_follows_amazons_own_redirector(monkeypatch):
    hops = {
        "https://a.co/d/abc": "https://www.amazon.com/gp/r.html?C=1&U=x",
        "https://www.amazon.com/gp/r.html?C=1&U=x": "/dp/B09V3KXJPB?ref=share",
    }

    async def reply(url: str, _kwargs: dict[str, Any]):
        return raw(url, status=302, headers={"Location": hops[url]})

    sent = answering(monkeypatch, reply)
    target = await fetch.resolve_shortlink("https://a.co/d/abc")

    assert target == "https://www.amazon.com/dp/B09V3KXJPB?ref=share"
    assert [kwargs["url"] for kwargs in sent] == list(hops)


# --- other marketplaces' languages ---


def _german_fallback() -> str:
    return _fixture("product_fallback_real.html").replace(
        FALLBACK_PDP_MARKER,
        "Um Produktdetails zu sehen, lege diesen Artikel in deinen Einkaufswagen",
    )


def test_the_fallback_page_is_recognised_in_any_language():
    assert FALLBACK_PDP_MARKER not in _german_fallback()
    assert is_fallback_product_page(_german_fallback())
    assert not is_fallback_product_page(_fixture("product_full_real.html"))


async def test_any_price_less_page_takes_the_card_price(monkeypatch):
    page = _german_fallback().replace('id="priceNotAvailable_feature_div"', "")

    async def fetch_page(url: str, **_kwargs):
        html = _fixture("search_real.html") if "/s?" in url else page
        return FetchResult(status=200, html=html, url=url, cookies={})

    async def fetch_aod_html(*_args, **_kwargs):
        return None

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    items = await scrape_products(
        _input("https://www.amazon.com/s?k=wireless+mouse", maxItemsPerStartUrl=1)
    )

    assert items[0]["price"] == {"value": 14.88, "currency": "USD"}
    assert items[0]["priceSource"] == "search_card"


def test_a_ratings_count_is_read_whatever_the_label_says():
    html = _fixture("search_real.html").replace(
        'aria-label="45,355 ratings"', 'aria-label="45.355 Sternebewertungen"'
    )

    cards = parse_search_page(html, domain="www.amazon.de")

    assert cards[0]["reviewsCount"] == 45355


# --- settings, progress, cancellation and the text ---


def test_a_malformed_wave_size_falls_back_instead_of_failing(monkeypatch):
    monkeypatch.setenv("AMAZON_DETAIL_CONCURRENCY", "sixteen")
    assert scraper._env_int("AMAZON_DETAIL_CONCURRENCY", 16) == 16
    monkeypatch.setenv("AMAZON_DETAIL_CONCURRENCY", "8")
    assert scraper._env_int("AMAZON_DETAIL_CONCURRENCY", 16) == 8


async def test_the_product_fetch_and_location_setup_report_progress(monkeypatch):
    async def get_location_session(*_args, **_kwargs):
        return None

    async def fetch_page(url: str, **_kwargs):
        return FetchResult(
            status=200, html=_fixture("product.html"), url=url, cookies={}
        )

    monkeypatch.setattr(scraper, "get_location_session", get_location_session)
    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    stages: list[str] = []

    async def heard(message: str) -> None:
        stages.append(message)

    await scrape_products(
        _input(
            "https://www.amazon.com/dp/B07CMS5Q6P",
            zipCode="10001",
            countryCode="US",
            maxOffers=0,
        ),
        on_stage=heard,
    )

    assert stages == [
        "setting the delivery location",
        "fetching product page",
        "product page fetched",
    ]


async def test_stopping_at_the_limit_cancels_the_details_still_loading(monkeypatch):
    cancelled: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        if "/s?" in url:
            html = _fixture("search_real.html")
        elif "B004YAVF8I" in url:
            html = _fixture("product.html")
        else:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(url)
                raise
        return FetchResult(status=200, html=html, url=url, cookies={})

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        _input(
            "https://www.amazon.com/s?k=wireless+mouse",
            maxItemsPerStartUrl=3,
            maxOffers=0,
        ),
        limit=1,
    )

    # Cancelled by the time the call returns, not later by the GC's finaliser.
    assert len(items) == 1
    assert len(cancelled) == 2


def test_the_text_answers_author_stock_and_spec_questions(monkeypatch):
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", "test-account")
    server = importlib.import_module("proprietary.amazon.server")
    product = {
        "title": "A Book",
        "asin": "B1",
        "url": "https://www.amazon.com/dp/B1",
        "author": "Jane Doe",
        "inStockText": "Only 3 left in stock.",
        "productOverview": [
            {"name": f"Spec {n}", "value": f"value {n}"} for n in range(10)
        ],
    }

    shown = json.loads(json.dumps(server._projected(product)))

    assert shown["author"] == "Jane Doe"
    assert shown["inStockText"] == "Only 3 left in stock."
    assert list(shown["specs"]) == [f"Spec {n}" for n in range(6)]
