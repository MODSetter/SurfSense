from __future__ import annotations

from pathlib import Path

from app.proprietary.platforms.amazon import AmazonScrapeInput, scrape_products, scraper
from app.proprietary.platforms.amazon.fetch import FetchResult
from app.proprietary.platforms.amazon.url_resolver import resolve_url

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _response(url: str, html: str, status: int = 200) -> FetchResult:
    return FetchResult(status=status, html=html, url=url, cookies={})


async def test_product_flow_emits_parsed_item(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B09V3KXJPB"}]
        )
    )

    assert len(items) == 1
    assert items[0]["asin"] == "B09V3KXJPB"
    assert items[0]["title"] == "Example Wireless Headphones"


async def test_product_flow_maps_not_found_to_error_item(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, "", status=404)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B09V3KXJPB"}]
        )
    )

    assert items[0]["error"] == "product_not_found"


async def test_search_flow_honors_cap_and_stops_on_empty_page(monkeypatch):
    calls: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        calls.append(url)
        html = _fixture("search.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/s?k=headphones"}],
            maxItemsPerStartUrl=1,
            maxSearchPagesPerStartUrl=5,
            scrapeProductDetails=False,
        )
    )

    assert len(items) == 1
    assert items[0]["categoryPageData"]["position"] == 1
    assert len(calls) == 1


async def test_search_flow_threads_marketplace_locale_to_fetch(monkeypatch):
    calls: list[dict[str, object]] = []

    async def fetch_page(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return _response(url, _fixture("search.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.co.uk/s?k=headphones"}],
            maxItemsPerStartUrl=1,
            scrapeProductDetails=False,
        )
    )

    assert len(items) == 1
    assert calls[0]["country"] == "gb"
    assert calls[0]["accept_language"] == "en-GB"


async def test_search_flow_returns_no_results_error(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, "<html></html>")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/s?k=missing"}],
            scrapeProductDetails=False,
        )
    )

    assert items[0]["error"] == "no_results_found"


async def test_product_flow_enriches_offers_and_seller(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("product.html"))

    async def fetch_aod_html(*_args, **_kwargs):
        return _fixture("offers.html")

    async def fetch_seller_html(*_args, **_kwargs):
        return _fixture("seller.html")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    monkeypatch.setattr(scraper, "fetch_seller_html", fetch_seller_html)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B09V3KXJPB"}],
            maxOffers=1,
            scrapeSellers=True,
        )
    )

    assert len(items[0]["offers"]) == 1
    assert items[0]["offers"][0]["seller"]["averageRating"] == 4.8
    assert items[0]["seller"]["reviewsCount"] == 1875


async def test_bestsellers_card_only_flow(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("bestsellers.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[
                {
                    "url": (
                        "https://www.amazon.com/Best-Sellers-Electronics/"
                        "zgbs/electronics"
                    )
                }
            ],
            maxItemsPerStartUrl=2,
            scrapeProductDetails=False,
        )
    )

    assert [item["bestsellerPageData"]["rank"] for item in items] == [1, 2]


async def test_shortlink_resolves_and_dispatches(monkeypatch):
    async def resolve(_url: str):
        return "https://www.amazon.com/dp/B09V3KXJPB"

    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "resolve_shortlink", resolve)
    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(categoryOrProductUrls=[{"url": "https://a.co/d/example"}])
    )

    assert items[0]["asin"] == "B09V3KXJPB"
    assert items[0]["input"] == "https://a.co/d/example"


async def test_product_flow_expands_variants_and_attaches_prices(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": "https://www.amazon.com/dp/B09V3KXJPB"}],
            maxProductVariantsAsSeparateResults=1,
            scrapeProductVariantPrices=True,
        )
    )

    assert [item["asin"] for item in items] == ["B09V3KXJPB", "B09V3KXJP1"]
    assert items[1]["originalAsin"] == "B09V3KXJPB"
    variant = next(
        detail
        for detail in items[0]["variantDetails"]
        if detail["asin"] == "B09V3KXJP1"
    )
    assert variant["price"]["value"] == 49.99


async def test_route_outside_location_allowlist_skips_session_mint(monkeypatch):
    calls = 0

    async def get_location_session(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(scraper, "get_location_session", get_location_session)
    resolved = resolve_url("https://www.amazon.com/dp/B09V3KXJPB")
    assert resolved is not None
    context = await scraper._location_context(
        resolved,
        AmazonScrapeInput(
            categoryOrProductUrls=[{"url": resolved.url}],
            zipCode="10001",
            locationDeliverableRoutes=["OFFERS"],
        ),
        "PRODUCT",
    )

    assert context == (None, None, None, None)
    assert calls == 0
