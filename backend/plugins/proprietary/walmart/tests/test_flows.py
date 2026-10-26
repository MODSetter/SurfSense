from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from proprietary.walmart import (
    WalmartReviewsInput,
    WalmartScrapeInput,
    scrape_products,
    scrape_reviews,
    scraper,
)
from proprietary.walmart.fetch import FetchResult

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


def _reviews_html(ids: list[str], *, last_page: int | None = None) -> str:
    """A reviews page holding ``ids``, its pagination naming ``last_page``."""
    reviews: dict = {"customerReviews": [{"reviewId": i, "rating": 5} for i in ids]}
    if last_page is not None:
        reviews["pagination"] = {
            "pages": [{"num": 1}, {"gap": True}, {"num": last_page}]
        }
    initial = {"data": {"reviews": reviews}}
    blob = json.dumps({"props": {"pageProps": {"initialData": initial}}})
    return f'<script id="__NEXT_DATA__" type="application/json">{blob}</script>'


def _page_number(url: str) -> int:
    return int(parse_qs(urlparse(url).query)["page"][0])


async def test_product_slug_url_is_requested_directly_when_switched_on(
    monkeypatch,
):
    """/ip/{id} redirects to the slug path, so the slug path is asked for directly."""
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setenv("WALMART_CANONICAL_URL", "1")
    await scrape_products(
        WalmartScrapeInput(
            startUrls=[
                "https://www.walmart.com/ip/Midea-AC/212092810?classType=VARIANT&athbdg=L1",
                "212092810",
            ]
        )
    )

    assert asked == [
        "https://www.walmart.com/ip/Midea-AC/212092810",
        "https://www.walmart.com/ip/212092810",
    ]


async def test_product_pages_are_requested_by_id_by_default(monkeypatch):
    """The direct slug hit is off until it passes the block-rate gate."""
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        return _response(url, _fixture("product.html"))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.delenv("WALMART_CANONICAL_URL", raising=False)
    await scrape_products(
        WalmartScrapeInput(startUrls=["https://www.walmart.com/ip/Midea-AC/212092810"])
    )

    assert asked == ["https://www.walmart.com/ip/212092810"]


async def test_detailed_items_keep_the_cards_provenance(monkeypatch):
    """The search URL stays the input, and the card's sponsored flag survives."""
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        if "/ip/" in url:
            return _response(url, _fixture("product_variant.html"))
        html = _fixture("listing_variant.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    search = "https://www.walmart.com/search?q=dish+soap"
    items = await scrape_products(
        WalmartScrapeInput(startUrls=[search], maxItemsPerStartUrl=1)
    )

    (item,) = items
    assert item["input"] == search
    assert item["sponsored"] is True
    assert item["stars"] == 4.6
    assert len(asked) == 2  # one listing page, one product page


async def test_a_failed_detail_yields_its_card_without_another_listing_fetch(
    monkeypatch,
):
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        if "791595618" in url:
            return None  # every proxy exit blocked
        if "/ip/" in url:
            return _response(url, _fixture("product.html"))
        html = _fixture("listing.html") if "page=1" in url else "<html></html>"
        return _response(url, html)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    search = "https://www.walmart.com/search?q=laptop"
    items = await scrape_products(
        WalmartScrapeInput(startUrls=[search], maxItemsPerStartUrl=2)
    )

    assert [item.get("error") for item in items] == [None, None]
    card, detailed = items
    assert card["usItemId"] == "791595618"
    assert card["price"] == {"value": 79.99, "currency": "USD"}
    assert card["detailsError"].startswith("product_not_found")
    assert card["input"] == search
    assert "detailsError" not in detailed
    assert not any("page=2" in url for url in asked)


async def test_the_next_listing_page_loads_while_details_are_in_flight(monkeypatch):
    """A page short of the cap starts the next page's fetch alongside its details."""
    asked: list[str] = []
    page_two_asked = asyncio.Event()

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        if "/ip/" in url:
            # Times out unless page 2 is fetched while this detail is in flight.
            await asyncio.wait_for(page_two_asked.wait(), timeout=2)
            return _response(url, _fixture("product.html"))
        page = _page_number(url)
        if page == 2:
            page_two_asked.set()
        html = {1: "listing.html", 2: "listing_variant.html"}.get(page)
        return _response(url, _fixture(html) if html else "<html></html>")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        WalmartScrapeInput(
            startUrls=["https://www.walmart.com/search?q=laptop"],
            maxItemsPerStartUrl=4,
        )
    )

    assert len(items) == 4
    assert [_page_number(url) for url in asked if "/search" in url] == [1, 2]


async def test_reviews_skip_repeats_across_pages_and_still_fill_the_cap(monkeypatch):
    """Page 2 repeats page 1's last review; it is skipped and not counted."""
    pages = {1: ["r1", "r2", "r3"], 2: ["r3", "r4", "r5"]}

    async def fetch_page(url: str, **_kwargs):
        ids = pages.get(_page_number(url), [])
        return _response(url, _reviews_html(ids, last_page=9) if ids else "")

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=4)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2", "r3", "r4"]


async def test_reviews_stop_at_the_last_page_the_pagination_names(monkeypatch):
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        ids = {1: ["r1", "r2"], 2: ["r3"]}.get(_page_number(url), ["r9"])
        return _response(url, _reviews_html(ids, last_page=2))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=100)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2", "r3"]
    assert len(asked) == 2


class InFlight:
    """Counts fetches running at once, the most seen, and each URL asked."""

    def __init__(self) -> None:
        self.now = 0
        self.most = 0
        self.asked: list[str] = []

    async def __call__(self, url: str, answer, delay: float = 0.01):
        self.asked.append(url)
        self.now += 1
        self.most = max(self.most, self.now)
        try:
            await asyncio.sleep(delay)
            return answer
        finally:
            self.now -= 1


async def test_review_pages_one_and_two_go_out_together(monkeypatch):
    page_two_asked = asyncio.Event()

    async def fetch_page(url: str, **_kwargs):
        page = _page_number(url)
        if page == 2:
            page_two_asked.set()
        else:
            # Times out unless page 2 was asked while page 1 is in flight.
            await asyncio.wait_for(page_two_asked.wait(), timeout=2)
        ids = [f"p{page}r{n}" for n in range(10)]
        return _response(url, _reviews_html(ids, last_page=9))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=20)
    )

    assert len(items) == 20


async def test_review_pages_run_side_by_side_up_to_the_cap_and_one_more(monkeypatch):
    """200 reviews: page 1's pagination says 30 pages; 21 are fetched, 8 at once."""
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        page = _page_number(url)
        ids = [f"p{page}r{n}" for n in range(10)]
        return await flight(url, _response(url, _reviews_html(ids, last_page=30)))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(WalmartReviewsInput(itemIds=["212092810"]))

    assert [item["reviewId"] for item in items] == [
        f"p{page}r{n}" for page in range(1, 21) for n in range(10)
    ]
    pages = sorted({_page_number(url) for url in flight.asked})
    assert pages[:20] == list(range(1, 21)) and max(pages) <= 21
    assert flight.most == 8


async def test_review_pages_go_one_at_a_time_when_their_end_is_unknown(monkeypatch):
    """Without pagination nothing says how far the reviews go: no pages past it."""
    flight = InFlight()
    pages = {1: ["r1", "r2"], 2: ["r3"], 3: ["r4"]}

    async def fetch_page(url: str, **_kwargs):
        ids = pages.get(_page_number(url), [])
        html = _reviews_html(ids) if ids else ""
        return await flight(url, _response(url, html))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=100)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2", "r3", "r4"]
    assert [_page_number(url) for url in flight.asked] == [1, 2, 3, 4]
    assert flight.most == 2  # pages 1 and 2 only


async def test_start_urls_run_side_by_side_and_keep_their_order(monkeypatch):
    flight = InFlight()
    product = _fixture("product.html").replace("212092810", "{id}")
    slow = {"1000001": 0.3, "1000002": 0.1, "1000003": 0.01}

    async def fetch_page(url: str, **_kwargs):
        item_id = url.rsplit("/", 1)[-1]
        html = product.replace("{id}", item_id)
        return await flight(url, _response(url, html), slow[item_id])

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_products(
        WalmartScrapeInput(
            startUrls=[f"https://www.walmart.com/ip/{i}" for i in slow],
        )
    )

    assert [item["usItemId"] for item in items] == list(slow)
    assert flight.most == 3


async def test_item_ids_run_side_by_side_and_keep_their_order(monkeypatch):
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        item_id = urlparse(url).path.rsplit("/", 1)[-1]
        ids = [f"{item_id}-r1"]
        delay = 0.3 if item_id == "1000001" else 0.01
        html = _reviews_html(ids, last_page=1)
        return await flight(url, _response(url, html), delay)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["1000001", "1000002"], maxReviews=5)
    )

    assert [item["reviewId"] for item in items] == ["1000001-r1", "1000002-r1"]
    assert flight.most >= 2


async def test_parallel_off_fetches_one_page_at_a_time(monkeypatch):
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        page = _page_number(url)
        ids = [f"p{page}r{n}" for n in range(10)]
        return await flight(url, _response(url, _reviews_html(ids, last_page=30)))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setenv("WALMART_PARALLEL", "0")
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["1000001", "1000002"], maxReviews=30)
    )

    assert len(items) == 60
    assert flight.most == 1


async def test_a_limit_stops_the_other_sources(monkeypatch):
    """Reaching the call's limit cancels the sources still running."""
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        delay = 0.01 if url.endswith("1000001") else 30
        return await flight(url, _response(url, _fixture("product.html")), delay)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await asyncio.wait_for(
        scrape_products(
            WalmartScrapeInput(
                startUrls=[
                    "https://www.walmart.com/ip/1000001",
                    "https://www.walmart.com/ip/1000002",
                ]
            ),
            limit=1,
        ),
        timeout=5,
    )

    assert len(items) == 1
    assert flight.now == 0


async def test_repeated_pages_end_a_walk_whose_end_is_unknown(monkeypatch):
    """No pagination, and every page repeats page 1: before, the walk ran on a
    page at a time to the 500-page limit for 3 reviews."""
    asked: list[str] = []

    async def fetch_page(url: str, **_kwargs):
        asked.append(url)
        return _response(url, _reviews_html(["r1", "r2", "r3"]))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=200)
    )

    assert [item["reviewId"] for item in items] == ["r1", "r2", "r3"]
    assert [_page_number(url) for url in asked] == [1, 2]


async def test_the_first_reviews_are_heard_before_the_last_page_loads(monkeypatch):
    """Items stream as their page is read, not once the whole source is done."""
    heard = asyncio.Event()

    async def fetch_page(url: str, **_kwargs):
        page = _page_number(url)
        if page == 3:
            # Times out unless page 1's reviews were heard before this page.
            await asyncio.wait_for(heard.wait(), timeout=2)
        ids = [f"p{page}r{n}" for n in range(10)]
        return _response(url, _reviews_html(ids, last_page=3))

    async def on_item(count: int) -> None:
        heard.set()

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(itemIds=["212092810"], maxReviews=30), on_item=on_item
    )

    assert len(items) == 30


async def test_parallel_off_fetches_the_next_listing_page_after_the_details(
    monkeypatch,
):
    """WALMART_PARALLEL=0 keeps the old serial order: no listing page prefetch."""
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        if "/ip/" in url:
            return await flight(url, _response(url, _fixture("product.html")))
        html = {1: "listing.html", 2: "listing_variant.html"}.get(_page_number(url))
        page = _fixture(html) if html else "<html></html>"
        return await flight(url, _response(url, page))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    monkeypatch.setenv("WALMART_PARALLEL", "0")
    items = await scrape_products(
        WalmartScrapeInput(
            startUrls=["https://www.walmart.com/search?q=laptop"],
            maxItemsPerStartUrl=4,
        )
    )

    assert len(items) == 4
    assert flight.most == 1
    kinds = ["detail" if "/ip/" in url else _page_number(url) for url in flight.asked]
    assert kinds == [1, "detail", "detail", 2, "detail", "detail"]


async def test_a_limit_mid_listing_stops_the_next_page_prefetch(monkeypatch):
    """The prefetched page is cancelled and awaited before the call returns."""
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        if "/ip/" in url:
            return await flight(url, _response(url, _fixture("product.html")))
        page = _page_number(url)
        html = _fixture("listing.html") if page == 1 else "<html></html>"
        return await flight(url, _response(url, html), 0.01 if page == 1 else 30)

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await asyncio.wait_for(
        scrape_products(
            WalmartScrapeInput(
                startUrls=["https://www.walmart.com/search?q=laptop"],
                maxItemsPerStartUrl=4,
            ),
            limit=1,
        ),
        timeout=5,
    )

    assert len(items) == 1
    assert any(_page_number(url) == 2 for url in flight.asked if "/search" in url)
    assert flight.now == 0


async def test_one_call_keeps_at_most_twelve_pages_in_flight(monkeypatch):
    """Four item ids at eight pages each share the call's bound."""
    flight = InFlight()

    async def fetch_page(url: str, **_kwargs):
        ids = [f"{url}-{n}" for n in range(10)]
        return await flight(url, _response(url, _reviews_html(ids, last_page=30)))

    monkeypatch.setattr(scraper, "fetch_page", fetch_page)
    items = await scrape_reviews(
        WalmartReviewsInput(
            itemIds=["1000001", "1000002", "1000003", "1000004"], maxReviews=100
        )
    )

    assert len(items) == 400
    assert flight.most == 12
