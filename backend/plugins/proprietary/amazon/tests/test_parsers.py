from __future__ import annotations

from pathlib import Path

from proprietary.amazon import fetch
from proprietary.amazon.fetch import (
    FetchResult,
    get_location_session,
    is_blocked,
    should_localize,
)
from proprietary.amazon.parsers import (
    _float,
    parse_aod_offers,
    parse_bestsellers_page,
    parse_product,
    parse_search_page,
    parse_seller,
)
from proprietary.amazon.tests._fake_http import answering, raw

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_product_parser_extracts_core_public_fields():
    item = parse_product(
        _fixture("product.html"),
        asin="B09V3KXJPB",
        url="https://www.amazon.com/dp/B09V3KXJPB",
    )

    assert item["title"] == "Example Wireless Headphones"
    assert item["price"] == {"value": 49.99, "currency": "USD"}
    assert item["listPrice"] == {"value": 79.99, "currency": "USD"}
    assert item["stars"] == 4.6
    assert item["reviewsCount"] == 1234
    assert item["inStock"] is True
    assert item["features"] == ["Long battery life", "Noise cancelling"]
    assert item["starsBreakdown"]["5star"] == 0.8
    assert "B09V3KXJP1" in item["variantAsins"]
    assert item["variantAttributes"][0]["name"] == "color_name"
    assert item["productPageReviews"][0]["id"] == "R1"


def test_block_detection_handles_status_and_markup():
    blocked = _fixture("blocked.html")
    assert is_blocked(blocked, 200)
    assert is_blocked("", 503)
    assert not is_blocked(_fixture("product.html"), 200)


def test_block_detection_handles_waf_header_and_body_markers():
    assert is_blocked(
        "<html>ordinary status</html>",
        200,
        {"X-Amzn-Waf-Action": "challenge"},
    )
    assert is_blocked(
        "<script src='https://token.awswaf.com/challenge.js'></script>", 200
    )
    assert is_blocked(
        '<meta http-equiv="refresh" content="5; URL=/s?bm-verify=x">', 200
    )


def test_float_handles_us_and_eu_price_formats():
    assert _float("1.234,56 €") == 1234.56
    assert _float("12,99 €") == 12.99
    assert _float("$1,234.56") == 1234.56
    assert _float("1234") == 1234.0


async def test_block_retry_proxy_uses_fresh_country_session(monkeypatch):
    """A retry leaves on a leased sticky exit, burned when Amazon refused it."""
    leased: list[tuple[str, str | None]] = []
    released: list[tuple[str, bool]] = []

    class Exit:
        def __init__(self, name: str) -> None:
            self.name = name

        def proxy_url(self) -> str:
            return f"http://{self.name}"

    def lease_exit(prefix: str, country: str | None = None) -> Exit:
        leased.append((prefix, country))
        return Exit(f"sticky-{len(leased)}")

    def release_exit(exit: Exit, *, burned: bool = False) -> None:
        released.append((exit.name, burned))

    async def reply(url: str, kwargs):
        blocked = kwargs["proxy"] in {"http://geo-fr", "http://sticky-1"}
        return raw(url, "Robot Check" if blocked else "<html>ok</html>")

    sent = answering(monkeypatch, reply)
    monkeypatch.setattr(
        fetch, "get_geo_proxy_url", lambda country=None: "http://geo-fr"
    )
    monkeypatch.setattr(fetch.sessions, "lease_exit", lease_exit)
    monkeypatch.setattr(fetch.sessions, "release_exit", release_exit)
    monkeypatch.setenv("AMAZON_HEDGE", "0")
    _notes, hedges, notes = fetch.start_call()
    try:
        result = await fetch.fetch_page("https://www.amazon.fr/s?k=x", country="fr")
    finally:
        fetch.end_call(hedges, notes)

    assert result is not None and result.html == "<html>ok</html>"
    assert [kwargs["proxy"] for kwargs in sent] == [
        "http://geo-fr",
        "http://sticky-1",
        "http://sticky-2",
    ]
    assert leased == [("amazon", "fr"), ("amazon", "fr")]
    assert released == [("sticky-1", True), ("sticky-2", False)]


def test_search_parser_extracts_cards_and_provenance():
    cards = parse_search_page(_fixture("search.html"), page=2)

    assert [card["asin"] for card in cards] == ["B09V3KXJPB", "B09V3KXJP1"]
    assert cards[0]["categoryPageData"] == {
        "position": 1,
        "page": 2,
        "isSponsored": False,
        "isBestSeller": True,
    }
    assert cards[1]["categoryPageData"]["isSponsored"] is True


def test_offer_and_seller_parsers():
    offers = parse_aod_offers(_fixture("offers.html"))
    seller = parse_seller(_fixture("seller.html"), seller_id="SELLER123")

    assert len(offers) == 2
    assert offers[0]["price"]["value"] == 47.5
    assert offers[0]["seller"]["id"] == "SELLER123"
    assert offers[0]["isPinnedOffer"] is True
    assert seller["name"] == "Example Retailer"
    assert seller["averageRating"] == 4.8
    assert seller["reviewsCount"] == 1875


def test_bestsellers_parser_extracts_ranked_products():
    items = parse_bestsellers_page(_fixture("bestsellers.html"))

    assert [item["asin"] for item in items] == ["B09V3KXJPB", "B09V3KXJP1"]
    assert [item["bestsellerPageData"]["rank"] for item in items] == [1, 2]


def test_location_route_filter_is_explicit():
    routes = ["PRODUCT", "OFFERS"]
    assert should_localize("product", routes)
    assert not should_localize("search", routes)


async def test_location_session_mints_once_and_reuses_cache(monkeypatch):
    fetch._location_sessions.clear()
    fetch._location_failures.clear()
    calls: list[str] = []

    class StickyExit:
        country = "us"

        @staticmethod
        def proxy_url() -> str:
            return "http://sticky-proxy"

    async def fetch_page(url: str, **_kwargs):
        calls.append(url)
        if len(calls) == 1:
            return FetchResult(
                status=200,
                html='<input name="anti-csrftoken-a2z" value="token-123">',
                url=url,
                cookies={"session-id": "session", "ubid-main": "ubid"},
            )
        return FetchResult(
            status=200,
            html='{"isValidAddress":1}',
            url=url,
            cookies={"session-id": "session"},
        )

    monkeypatch.setattr(fetch, "_lease_location_exit", lambda _country: StickyExit())
    monkeypatch.setattr(fetch, "fetch_page", fetch_page)

    first = await get_location_session(
        "www.amazon.com", zip_code="10001", country_code="US"
    )
    second = await get_location_session(
        "www.amazon.com", zip_code="10001", country_code="US"
    )

    assert first is second
    assert first is not None
    assert first.proxy == "http://sticky-proxy"
    assert first.country_code == "US"
    assert len(calls) == 2
