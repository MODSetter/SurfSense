"""Flows: overlapped product chain, page-filling search details, fallback prices,
and the per-route referer."""

from __future__ import annotations

import asyncio
from pathlib import Path

from proprietary.amazon import AmazonScrapeInput, fetch, scrape_products, scraper
from proprietary.amazon.fetch import FetchResult
from proprietary.amazon.tests._fake_http import answering, raw
from proprietary.scraping import http

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _response(url: str, html: str, status: int = 200) -> FetchResult:
    return FetchResult(status=status, html=html, url=url, cookies={})


def _input(url: str, **kwargs) -> AmazonScrapeInput:
    return AmazonScrapeInput(categoryOrProductUrls=[{"url": url}], **kwargs)


def _usd(value: float) -> dict[str, object]:
    return {"value": value, "currency": "USD"}


async def test_offers_panel_starts_before_the_product_page_finishes(monkeypatch):
    events: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        events.append("pdp-start")
        await asyncio.sleep(0.05)
        events.append("pdp-end")
        return _response(url, _fixture("product.html"))

    async def fetch_aod_html(*_args, **_kwargs):
        events.append("aod-start")
        return _fixture("offers.html")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    items = await scrape_products(
        _input("https://www.amazon.com/dp/B09V3KXJPB", maxOffers=2)
    )

    assert events.index("aod-start") < events.index("pdp-end")
    assert [offer["price"]["value"] for offer in items[0]["offers"]] == [47.5, 39.0]


async def test_featured_seller_starts_before_the_offers_panel_finishes(monkeypatch):
    events: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("product.html"))

    async def fetch_aod_html(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        events.append("aod-end")
        return _fixture("offers.html")

    async def fetch_seller_html(seller_id: str, *_args, **_kwargs):
        events.append(f"seller-start:{seller_id}")
        return _fixture("seller.html")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    monkeypatch.setattr(scraper, "fetch_seller_html", fetch_seller_html)
    items = await scrape_products(
        _input("https://www.amazon.com/dp/B09V3KXJPB", maxOffers=2, scrapeSellers=True)
    )

    assert events.index("seller-start:SELLER123") < events.index("aod-end")
    # The offer-only seller starts once the panel names it; none starts twice.
    assert events.count("seller-start:SELLER123") == 1
    assert "seller-start:SELLER456" in events
    assert items[0]["seller"]["reviewsCount"] == 1875
    assert items[0]["offers"][1]["seller"]["averageRating"] == 4.8


async def test_failed_product_page_cancels_the_offers_panel(monkeypatch):
    cancelled = asyncio.Event()

    async def fetch_page(url: str, **_kwargs):
        await asyncio.sleep(0.01)  # the panel request is under way by now
        return _response(url, "", status=404)

    async def fetch_aod_html(*_args, **_kwargs):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    items = await scrape_products(
        _input("https://www.amazon.com/dp/B09V3KXJPB", maxOffers=1)
    )
    await asyncio.wait_for(cancelled.wait(), timeout=1)

    assert items[0]["error"] == "product_not_found"


async def test_search_details_fill_the_cap_from_page_one_first(monkeypatch):
    pages: list[str] = []
    products: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        if "/s?" in url:
            pages.append(url)
            return _response(url, _fixture("search_real.html"))
        products.append(url)
        if "B0F5HPCLGB" in url:
            return _response(url, "", status=404)
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        _input("https://www.amazon.com/s?k=wireless+mouse", maxItemsPerStartUrl=4)
    )

    found = [item["asin"] for item in items if "error" not in item]
    # The failed detail is replaced by the page's next card, the sponsored one,
    # unwrapped to its product page; page 2 is never fetched.
    assert found == ["B004YAVF8I", "B0HBJHY9M1", "B07CMS5Q6P", "B0CG1LGWR6"]
    assert sum("error" in item for item in items) == 1
    assert len(pages) == 1
    assert not any("/sspa/click" in url for url in products)
    assert any("/dp/B0CG1LGWR6/ref=sr_1_10_sspa" in url for url in products)
    # The repeated card is fetched once.
    assert sum("B0F5HPCLGB" in url for url in products) == 1


async def test_search_cards_are_unique_and_absolute_across_pages(monkeypatch):
    second_page = """
    <div data-component-type="s-search-result" data-asin="B004YAVF8I">
      <h2><a href="/dp/B004YAVF8I"><span>Repeat</span></a></h2>
    </div>
    <div data-component-type="s-search-result" data-asin="B09V3KXJPB">
      <h2><a href="/dp/B09V3KXJPB"><span>New</span></a></h2>
    </div>
    """

    async def fetch_page(url: str, **_kwargs):
        html = second_page if "page=2" in url else _fixture("search_real.html")
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        _input(
            "https://www.amazon.com/s?k=wireless+mouse",
            maxItemsPerStartUrl=6,
            maxSearchPagesPerStartUrl=2,
            scrapeProductDetails=False,
        )
    )

    asins = [item["asin"] for item in items]
    assert len(asins) == len(set(asins)) == 6
    # Page 1 had 6 cards, so page 2's second card (its first new one) is position 8.
    assert items[-1]["categoryPageData"] == {
        "position": 8,
        "page": 2,
        "isSponsored": False,
        "isBestSeller": False,
    }


async def test_search_and_bestseller_pages_skip_the_google_referer(monkeypatch):
    calls: list[bool] = []

    async def fetch_page(url: str, **kwargs):
        calls.append(kwargs.get("google_referer", True))
        html = "bestsellers_real.html" if "bestsellers" in url else "search.html"
        return _response(url, _fixture(html))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    for url in (
        "https://www.amazon.com/s?k=headphones",
        "https://www.amazon.com/gp/bestsellers/electronics",
    ):
        await scrape_products(
            _input(url, maxItemsPerStartUrl=1, scrapeProductDetails=False)
        )
    monkeypatch.setenv("AMAZON_NO_GOOGLE_REFERER", "0")
    await scrape_products(
        _input(
            "https://www.amazon.com/s?k=headphones",
            maxItemsPerStartUrl=1,
            scrapeProductDetails=False,
        )
    )

    assert calls == [False, False, True]


async def test_offers_panel_is_requested_as_an_xhr_from_the_product_page(monkeypatch):
    sent: list[dict[str, str] | None] = []

    async def fetch_html(_url: str, **kwargs):
        sent.append(kwargs.get("headers"))
        return "<html></html>"

    monkeypatch.setattr(fetch, "fetch_html", fetch_html)
    await fetch.fetch_aod_html("B07CMS5Q6P", "www.amazon.com")
    # The search referer's switch no longer turns the panel's shape off too.
    monkeypatch.setenv("AMAZON_NO_GOOGLE_REFERER", "0")
    await fetch.fetch_aod_html("B07CMS5Q6P", "www.amazon.com")
    monkeypatch.setenv("AMAZON_AOD_XHR", "0")
    await fetch.fetch_aod_html("B07CMS5Q6P", "www.amazon.com")

    xhr = {
        "Referer": "https://www.amazon.com/dp/B07CMS5Q6P",
        "X-Requested-With": "XMLHttpRequest",
    }
    assert sent == [xhr, xhr, None]


async def test_fetch_page_turns_off_the_google_referer_on_request(monkeypatch):
    async def reply(url: str, _kwargs):
        return raw(url, "<html>ok</html>")

    seen = answering(monkeypatch, reply)
    await fetch.fetch_page("https://www.amazon.com/s?k=x", google_referer=False)
    await fetch.fetch_page("https://www.amazon.com/dp/B07CMS5Q6P")

    assert [kwargs["referer"] for kwargs in seen] == [None, http.GOOGLE]


async def test_fallback_search_detail_takes_the_card_price(monkeypatch):
    panels = 0

    async def fetch_page(url: str, **_kwargs):
        if "/s?" in url:
            return _response(url, _fixture("search_real.html"))
        return _response(url, _fixture("product_fallback_real.html"))

    async def fetch_aod_html(*_args, **_kwargs):
        nonlocal panels
        panels += 1

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    items = await scrape_products(
        _input("https://www.amazon.com/s?k=wireless+mouse", maxItemsPerStartUrl=1)
    )

    assert items[0]["asin"] == "B004YAVF8I"
    assert items[0]["price"] == _usd(14.88)
    assert items[0]["listPrice"] == _usd(17.99)
    assert items[0]["priceSource"] == "search_card"
    assert panels == 0


async def test_fallback_product_url_takes_the_pinned_offer(monkeypatch):
    panels = 0
    page = "product_fallback_real.html"

    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture(page))

    async def fetch_aod_html(*_args, **_kwargs):
        nonlocal panels
        panels += 1
        return _fixture("aod_real.html")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setattr(scraper, "fetch_aod_html", fetch_aod_html)
    fallback = await scrape_products(_input("https://www.amazon.com/dp/B07CMS5Q6P"))
    page = "product_full_real.html"
    full = await scrape_products(_input("https://www.amazon.com/dp/B07CMS5Q6P"))

    assert fallback[0]["price"] == _usd(29.99)
    assert fallback[0]["listPrice"] == _usd(49.99)
    assert fallback[0]["inStock"] is True
    assert fallback[0]["delivery"].startswith("FREE delivery")
    assert fallback[0]["priceSource"] == "offers"
    # max_offers=0: the panel only fills the price, it adds no offers.
    assert fallback[0]["offers"] == []
    assert full[0]["price"] == _usd(29.99)
    assert full[0]["priceSource"] == "product_page"
    # The panel is fetched for the fallback page only.
    assert panels == 1


async def test_bestsellers_flow_emits_each_product_once(monkeypatch):
    async def fetch_page(url: str, **_kwargs):
        return _response(url, _fixture("bestsellers_real.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        _input(
            "https://www.amazon.com/gp/bestsellers/electronics",
            maxItemsPerStartUrl=10,
            maxSearchPagesPerStartUrl=1,
            scrapeProductDetails=False,
        )
    )

    assert len({item["asin"] for item in items}) == len(items) == 5
    assert [item["bestsellerPageData"]["rank"] for item in items] == [1, 2, 3, 4, 5]
