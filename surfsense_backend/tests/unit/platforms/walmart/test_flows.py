from __future__ import annotations

from pathlib import Path

from app.proprietary.platforms.walmart import (
    WalmartReviewsInput,
    WalmartScrapeInput,
    scrape_products,
    scrape_reviews,
    scraper,
)
from app.proprietary.platforms.walmart.fetch import FetchResult

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
        WalmartScrapeInput(startUrls=["https://www.walmart.com/ip/212092810"])
    )

    assert len(items) == 1
    assert items[0]["usItemId"] == "212092810"
    assert items[0]["name"].startswith("Midea")


async def test_product_flow_maps_not_found_to_error_item(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, "", status=404)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        WalmartScrapeInput(startUrls=["https://www.walmart.com/ip/212092810"])
    )

    assert items[0]["error"] == "product_not_found"


async def test_listing_flow_card_only_honors_cap(monkeypatch):
    calls: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        calls.append(url)
        html = _fixture("listing.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        WalmartScrapeInput(
            startUrls=["https://www.walmart.com/search?q=laptop"],
            maxItemsPerStartUrl=1,
            includeDetails=False,
        )
    )

    assert len(items) == 1
    assert items[0]["usItemId"] == "791595618"
    assert len(calls) == 1


async def test_listing_flow_enriches_with_detail_pages(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        if "/ip/" in url:
            return _response(url, _fixture("product.html"))
        html = _fixture("listing.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        WalmartScrapeInput(
            startUrls=["https://www.walmart.com/search?q=laptop"],
            maxItemsPerStartUrl=2,
            includeDetails=True,
        )
    )

    # Both cards enrich to the same product fixture (detail fetch wins).
    assert all(item["longDescription"] for item in items)


async def test_invalid_url_yields_error_item(monkeypatch):
    items = await scrape_products(
        WalmartScrapeInput(startUrls=["https://example.com/not-walmart"])
    )
    assert items[0]["error"] == "invalid_url"


async def test_reviews_flow_paginates_until_empty(monkeypatch):
    calls: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        calls.append(url)
        html = _fixture("reviews.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=100)
    )

    assert len(items) == 2
    assert items[0]["reviewId"] == "296013686"
    # page=1 returned records, page=2 empty → stop. Two fetches total.
    assert len(calls) == 2


async def test_reviews_flow_honors_max_reviews(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("reviews.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=1)
    )

    assert len(items) == 1


async def test_reviews_flow_maps_empty_to_error_item(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, "<html></html>")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(WalmartReviewsInput(itemIds=["212092810"]))

    assert items[0]["error"] == "reviews_not_found"
