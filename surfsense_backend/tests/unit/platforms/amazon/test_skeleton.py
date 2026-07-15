"""Offline contract tests for the Amazon Product Scraper.

Deterministic (no network, no live Amazon HTML): asserts the input defaults, the
full output-item serialization contract, the error-item shape, and URL
classification. The live fetch / parse flows are exercised by the e2e script in
later milestones, not here.
"""

from __future__ import annotations

from app.proprietary.platforms.amazon import (
    AmazonScrapeInput,
    ErrorItem,
    ProductItem,
    scrape_products,
)
from app.proprietary.platforms.amazon.url_resolver import extract_asin, resolve_url

# A complete input payload should validate without removing optional fields.
_SPEC_INPUT = {
    "categoryOrProductUrls": [{"url": "https://www.amazon.com/s?k=keyboard"}],
    "maxItemsPerStartUrl": 100,
    "language": "en",
    "proxyCountry": "AUTO_SELECT_PROXY_COUNTRY",
    "maxSearchPagesPerStartUrl": 9999,
    "maxOffers": 0,
    "scrapeSellers": False,
    "useCaptchaSolver": False,
    "scrapeProductVariantPrices": False,
    "scrapeProductDetails": True,
    "countryCode": "US",
    "zipCode": "10001",
    "locationDeliverableRoutes": ["PRODUCT", "SEARCH", "OFFERS"],
}


def test_input_has_no_auth_fields():
    # Public, anonymous only: no auth-shaped field may exist on the input surface.
    forbidden = {"username", "password", "token", "login", "auth", "credentials"}
    assert forbidden.isdisjoint(AmazonScrapeInput.model_fields)


def test_scrape_input_defaults_match_contract():
    inp = AmazonScrapeInput(
        categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B0"}]
    )
    assert inp.maxItemsPerStartUrl is None
    assert inp.maxSearchPagesPerStartUrl == 9999
    assert inp.maxProductVariantsAsSeparateResults == 0
    assert inp.maxOffers == 0
    assert inp.proxyCountry == "AUTO_SELECT_PROXY_COUNTRY"
    assert inp.language is None
    assert inp.countryCode is None
    assert inp.zipCode is None
    assert inp.locationDeliverableRoutes == ["PRODUCT", "SEARCH", "OFFERS"]
    assert inp.scrapeSellers is False
    assert inp.useCaptchaSolver is False
    assert inp.scrapeProductVariantPrices is False
    assert inp.scrapeProductDetails is True


def test_complete_payload_validates():
    inp = AmazonScrapeInput(**_SPEC_INPUT)
    assert inp.maxItemsPerStartUrl == 100
    assert inp.countryCode == "US"


def test_input_allows_extra_inert_fields():
    # extra="allow": unknown add-ons (e.g. upstream proxy config) are accepted.
    inp = AmazonScrapeInput(
        categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B0"}],
        proxyConfiguration={"useResidentialProxy": True},
        someFutureAddon=123,
    )
    assert inp.model_dump().get("someFutureAddon") == 123


def test_output_item_serializes_full_shape():
    item = ProductItem(asin="B08EXAMPLE01").to_output()
    assert item["asin"] == "B08EXAMPLE01"
    # Unsourced scalars are still present as None (consumers never KeyError).
    assert item["title"] is None
    assert item["monthlyPurchaseVolume"] is None
    # List fields default to [].
    assert item["features"] == []
    assert item["offers"] == []
    assert item["productPageReviews"] == []
    # Typed-but-unset nested objects are None.
    assert item["price"] is None
    assert item["seller"] is None


def test_stars_breakdown_round_trips_digit_keys():
    item = ProductItem(
        stars=4.8, starsBreakdown={"5star": 0.86, "1star": 0.01}
    ).to_output()
    # by_alias serialization restores Amazon's digit-prefixed keys.
    assert item["starsBreakdown"]["5star"] == 0.86
    assert item["starsBreakdown"]["1star"] == 0.01
    assert item["starsBreakdown"]["4star"] is None


def test_error_item_shape():
    err = ErrorItem(
        error="product_not_found",
        errorDescription="Loaded a 404 page.",
        input="https://www.amazon.com/dp/B0XXXXXXXX",
        url="https://www.amazon.com/dp/B0XXXXXXXX",
    ).model_dump()
    assert set(err) >= {"error", "errorDescription", "input", "url"}
    assert err["error"] == "product_not_found"


def test_extract_asin():
    assert extract_asin("https://www.amazon.com/dp/B09X7MPX8L") == "B09X7MPX8L"
    assert extract_asin("https://www.amazon.com/gp/product/B09X7MPX8L/ref=x") == (
        "B09X7MPX8L"
    )
    assert extract_asin("https://www.amazon.com/s?k=keyboard") is None


def test_resolve_url_classifies_all_kinds():
    product = resolve_url("https://www.amazon.com/dp/B0EXAMPLE1")
    assert product is not None
    assert product.kind == "product"
    assert product.asin == "B0EXAMPLE1"
    assert product.marketplace == "com"

    search = resolve_url("https://www.amazon.com/s?k=keyboard")
    assert search is not None and search.kind == "search"

    # A category URL with no /s path but a bbn/rh query still classifies as search.
    category = resolve_url(
        "https://www.amazon.de/s?i=specialty-aps&bbn=16225007011&rh=n%3A16225007011"
    )
    assert category is not None
    assert category.kind == "search"
    assert category.marketplace == "de"

    bestsellers = resolve_url(
        "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics"
    )
    assert bestsellers is not None and bestsellers.kind == "bestsellers"

    shortened = resolve_url("https://a.co/d/abcd123")
    assert shortened is not None and shortened.kind == "shortened"


def test_resolve_url_rejects_non_amazon_and_unrecognized():
    assert resolve_url("https://example.com/dp/B08EXAMPLE1") is None
    # An Amazon host but an unrecognized path (e.g. the homepage) is unrecognized.
    assert resolve_url("https://www.amazon.com/") is None


async def test_iter_products_unrecognized_yields_error():
    # A junk / non-Amazon URL yields exactly one invalid_url error item.
    items = await scrape_products(
        AmazonScrapeInput(categoryOrProductUrls=[{"url": "https://example.com/foo"}])
    )
    assert len(items) == 1
    assert items[0]["error"] == "invalid_url"
    assert items[0]["input"] == "https://example.com/foo"


def test_valid_product_url_is_ready_for_dispatch():
    resolved = resolve_url("https://www.amazon.com/dp/B0EXAMPLE1")
    assert resolved is not None
    assert resolved.kind == "product"


async def test_iter_products_missing_url_key_yields_error():
    # An entry without a "url" key is treated as an invalid start URL, not a crash.
    items = await scrape_products(
        AmazonScrapeInput(categoryOrProductUrls=[{"noturl": "x"}])
    )
    assert len(items) == 1
    assert items[0]["error"] == "invalid_url"
