"""Parsers against trimmed real Amazon pages (captured 2026-10-14, scrubbed).

``search_real.html`` keeps the brand-banner nodes between product cards, adds
one sponsored ``/sspa/click`` card and repeats one card, as live pages do.
"""

from __future__ import annotations

import re
from pathlib import Path

from proprietary.amazon.parsers import (
    FALLBACK_PDP_MARKER,
    _count,
    parse_aod_offers,
    parse_bestsellers_page,
    parse_product,
    parse_search_page,
)
from proprietary.amazon.url_resolver import resolve_url

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _usd(value: float) -> dict[str, object]:
    return {"value": value, "currency": "USD"}


def test_search_cards_skip_banners_and_count_positions_in_page_order():
    cards = parse_search_page(_fixture("search_real.html"), page=1)

    assert [card["asin"] for card in cards] == [
        "B004YAVF8I",
        "B0F5HPCLGB",
        "B0HBJHY9M1",
        "B07CMS5Q6P",
        "B0CG1LGWR6",
        "B0F5HPCLGB",
    ]
    # Banner nodes no longer shift the count: the first product is position 1.
    assert [card["categoryPageData"]["position"] for card in cards[:4]] == [
        1,
        2,
        3,
        4,
    ]


def test_search_card_counts_badges_and_list_price():
    cards = {
        card["asin"]: card
        for card in parse_search_page(_fixture("search_real.html"), page=1)
    }

    # aria-label "45,355 ratings", not the visible "(45.3K)".
    assert cards["B004YAVF8I"]["reviewsCount"] == 45355
    assert cards["B0F5HPCLGB"]["reviewsCount"] == 7547
    assert cards["B0HBJHY9M1"]["reviewsCount"] == 17
    # "Overall Pick" and "Limited time deal" badges are not Best Seller.
    assert cards["B004YAVF8I"]["categoryPageData"]["isBestSeller"] is False
    assert cards["B0F5HPCLGB"]["categoryPageData"]["isBestSeller"] is False
    assert cards["B07CMS5Q6P"]["categoryPageData"]["isBestSeller"] is True
    assert cards["B004YAVF8I"]["price"] == _usd(14.88)
    assert cards["B004YAVF8I"]["listPrice"] == _usd(17.99)
    assert cards["B0HBJHY9M1"]["listPrice"] is None


def test_sponsored_card_unwraps_to_its_product_page():
    card = next(
        card
        for card in parse_search_page(_fixture("search_real.html"), page=1)
        if card["asin"] == "B0CG1LGWR6"
    )

    assert card["url"].startswith(
        "https://www.amazon.com/LISEN-Cable-Charging-Charger/dp/B0CG1LGWR6/"
    )
    assert card["categoryPageData"]["isSponsored"] is True
    assert card["categoryPageData"]["position"] == 5
    resolved = resolve_url(card["url"])
    assert resolved is not None
    assert (resolved.kind, resolved.asin) == ("product", "B0CG1LGWR6")


def test_search_positions_continue_from_the_earlier_pages():
    html = """
    <div data-component-type="s-search-result" data-asin="">banner</div>
    <div data-component-type="s-search-result" data-asin="B09V3KXJPB">
      <h2><a href="/dp/B09V3KXJPB"><span>One</span></a></h2>
    </div>
    """

    cards = parse_search_page(html, page=2, offset=16)

    assert cards[0]["categoryPageData"]["position"] == 17


def test_search_capture_keeps_no_ad_tokens():
    # The ad pixels' p= blob encodes the client's IP prefix and the brand
    # widgets' tok= is a live token; the capture keeps only stand-ins.
    html = _fixture("search_real.html")
    pixels = re.findall(r"sponsored-ads\.amazon\.com/(?:imp|clk/)\?p=([^&\"']+)", html)
    tokens = re.findall(r"\btok=([^;\"]+)", html)
    assert len(pixels) == 48 and len(tokens) == 2
    assert set(pixels) == set(tokens) == {"x"}


def test_count_expands_abbreviations():
    assert _count("(45.3K)") == 45300
    assert _count("1.2M ratings") == 1200000
    assert _count("(17)") == 17
    assert _count(None) is None


def test_sspa_and_store_urls_are_not_search_pages():
    sponsored = resolve_url(
        "https://www.amazon.com/sspa/click?ie=UTF8&spc=x"
        "&url=%2FLISEN-Cable%2Fdp%2FB0CG1LGWR6%2Fref%3Dsr_1_1_sspa"
    )
    assert sponsored is not None
    assert (sponsored.kind, sponsored.asin) == ("product", "B0CG1LGWR6")
    assert resolve_url("https://www.amazon.com/sspa/click?ie=UTF8") is None
    assert resolve_url("https://www.amazon.com/stores/page/ABC") is None
    assert resolve_url("https://www.amazon.com/s?k=mouse").kind == "search"
    assert resolve_url("https://www.amazon.com/s/ref=nb_sb_noss").kind == "search"


def test_full_product_page_reads_list_price_badge_and_reviews_link():
    item = parse_product(
        _fixture("product_full_real.html"),
        asin="B07CMS5Q6P",
        url="https://www.amazon.com/dp/B07CMS5Q6P",
    )

    assert item["price"] == _usd(29.99)
    # The struck-through list price, not the per-unit price.
    assert item["listPrice"] == _usd(49.99)
    assert item["isAmazonChoice"] is True
    assert item["amazonChoiceText"] == "Amazon's Choice"
    assert item["reviewsLink"] == "https://www.amazon.com/product-reviews/B07CMS5Q6P"
    assert item["inStock"] is True


def test_list_price_needs_a_strike_and_must_exceed_the_price():
    per_unit = """
    <span id="productTitle">Cable 2-pack</span>
    <div id="corePriceDisplay_desktop_feature_div">
      <span class="a-price"><span class="a-offscreen">$9.99</span></span>
    </div>
    <div id="centerCol">
      <span class="a-price a-text-price"><span class="a-offscreen">$5.00</span></span>
    </div>
    """
    not_higher = """
    <span id="productTitle">Cable</span>
    <div id="corePriceDisplay_desktop_feature_div">
      <span class="a-price"><span class="a-offscreen">$9.99</span></span>
      <span class="a-price" data-a-strike="true"><span class="a-offscreen">$9.99</span></span>
    </div>
    """
    url = "https://www.amazon.com/dp/B09V3KXJPB"

    assert parse_product(per_unit, asin="B09V3KXJPB", url=url)["listPrice"] is None
    assert parse_product(not_higher, asin="B09V3KXJPB", url=url)["listPrice"] is None


def test_amazon_choice_explainer_alone_is_not_the_badge():
    html = """
    <span id="productTitle">Mouse</span>
    <div id="acBadge_feature_div">
      <div class="a-popover-preload">Amazon's Choice highlights highly rated products</div>
    </div>
    """

    item = parse_product(
        html, asin="B09V3KXJPB", url="https://www.amazon.com/dp/B09V3KXJPB"
    )

    assert item["isAmazonChoice"] is False
    assert item["amazonChoiceText"] is None


def test_fallback_product_page_has_no_price_and_carries_the_marker():
    html = _fixture("product_fallback_real.html")

    item = parse_product(
        html, asin="B07CMS5Q6P", url="https://www.amazon.com/dp/B07CMS5Q6P"
    )

    assert item["title"].startswith("Logitech G305")
    assert item["price"] is None
    assert FALLBACK_PDP_MARKER in html
    assert FALLBACK_PDP_MARKER not in _fixture("product_full_real.html")


def test_offers_panel_reads_prices_and_pins_the_featured_offer():
    offers = parse_aod_offers(_fixture("aod_real.html"))

    assert len(offers) == 4
    assert offers[0]["isPinnedOffer"] is True
    assert offers[0]["price"] == _usd(29.99)
    assert offers[0]["listPrice"] == _usd(49.99)
    assert offers[0]["condition"] == "New"
    assert offers[0]["seller"]["name"] == "Amazon.com"
    assert [offer["price"]["value"] for offer in offers[1:]] == [25.08, 25.38, 34.99]
    assert not any(offer["isPinnedOffer"] for offer in offers[1:])
    assert offers[3]["seller"]["id"] == "A2K7RN1DSQCI9O"


def test_bestsellers_page_yields_each_product_once_with_rank_and_price():
    items = parse_bestsellers_page(_fixture("bestsellers_real.html"))

    assert [item["asin"] for item in items] == [
        "B08JHCVHTY",
        "B0DCH8VDXF",
        "B0GJTFXNRX",
        "B0FQFB8FMG",
        "B0DJGDC3BD",
    ]
    assert [item["bestsellerPageData"]["rank"] for item in items] == [1, 2, 3, 4, 5]
    assert [item["price"]["value"] for item in items] == [
        11.99,
        19.0,
        24.0,
        199.0,
        39.99,
    ]
