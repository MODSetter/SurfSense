"""Orchestrate public Walmart product discovery, enrichment, and reviews.

Two streaming cores: :func:`iter_products` dispatches each start URL to a product
or listing flow, and :func:`iter_reviews` paginates the public reviews page per
item id. Network and parsing concerns stay isolated in their own modules so
markup changes and retry policy can be tested independently.

The failure model is in-stream error items (dicts with an ``error`` key), never
exceptions — identical to the Amazon scraper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .fetch import fetch_page, gather_bounded
from .next_data import extract_next_data
from .parsers import parse_listing_page, parse_product, parse_reviews_page
from .schemas import (
    ErrorItem,
    ProductItem,
    ReviewItem,
    WalmartReviewsInput,
    WalmartScrapeInput,
)
from .url_resolver import ResolvedUrl, extract_item_id, resolve_url

__all__ = ["iter_products", "iter_reviews", "scrape_products", "scrape_reviews"]

_DETAIL_CONCURRENCY = 6
_SEARCH_PAGE_LIMIT = 25  # Walmart caps result pagination at 25 pages.
_REVIEWS_PAGE_LIMIT = 500  # 10 reviews/page → 5000-review safety ceiling.
_DEFAULT_ITEMS_PER_START_URL = 40

# Friendly sort → Walmart's ``sort`` query value on the reviews page.
_REVIEW_SORT = {
    "most-recent": "submission-desc",
    "most-helpful": "helpful",
    "rating-high": "rating-desc",
    "rating-low": "rating-asc",
}


def _error(
    code: str, description: str, *, input_url: str | None, url: str | None = None
) -> dict[str, Any]:
    return ErrorItem(
        error=code,
        errorDescription=description,
        input=input_url,
        url=url or input_url,
    ).model_dump()


def _page_url(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _product_url(item_id: str) -> str:
    return f"https://www.walmart.com/ip/{item_id}"


def _reviews_url(item_id: str, page: int, sort: str) -> str:
    query = urlencode(
        {"page": page, "sort": sort, "entryPoint": "viewAllReviewsBottom"}
    )
    return f"https://www.walmart.com/reviews/product/{item_id}?{query}"


# --------------------------------------------------------------------------- #
# Product / listing flows.                                                    #
# --------------------------------------------------------------------------- #


async def _product_flow(
    resolved: ResolvedUrl, input_model: WalmartScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Fetch and parse one product detail page."""
    url = _product_url(resolved.item_id) if resolved.item_id else resolved.url
    response = await fetch_page(url, country=input_model.country)
    if response is None:
        yield _error(
            "product_not_found",
            "The product page could not be loaded after retrying proxy exits.",
            input_url=resolved.url,
        )
        return
    if response.status in {404, 410}:
        yield _error(
            "product_not_found",
            "The product page was not found.",
            input_url=resolved.url,
        )
        return

    next_data = extract_next_data(response.html)
    fields = (
        parse_product(
            next_data,
            url=response.url,
            include_reviews_sample=input_model.includeReviewsSample,
        )
        if next_data
        else {}
    )
    if not fields.get("name"):
        yield _error(
            "product_not_found",
            "The response did not contain a recognizable product.",
            input_url=resolved.url,
            url=response.url,
        )
        return
    fields["input"] = resolved.url
    yield ProductItem(**fields).to_output()


async def _listing_flow(
    resolved: ResolvedUrl, input_model: WalmartScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Page through a search/category/browse listing and optionally enrich."""
    cap = (
        input_model.maxItemsPerStartUrl
        if input_model.maxItemsPerStartUrl is not None
        else _DEFAULT_ITEMS_PER_START_URL
    )
    max_pages = min(input_model.maxSearchPagesPerStartUrl, _SEARCH_PAGE_LIMIT)
    seen: set[str] = set()
    emitted = 0
    for page in range(1, max_pages + 1):
        response = await fetch_page(
            _page_url(resolved.url, page), country=input_model.country
        )
        next_data = extract_next_data(response.html) if response else None
        cards = parse_listing_page(next_data) if next_data else []
        cards = [c for c in cards if c["usItemId"] not in seen]
        for card in cards:
            seen.add(card["usItemId"])
        if not cards:
            if page == 1:
                yield _error(
                    "no_results_found",
                    "The listing page did not contain any products.",
                    input_url=resolved.url,
                )
            return
        cards = cards[: max(0, cap - emitted)]

        if not input_model.includeDetails:
            for card in cards:
                card["input"] = resolved.url
                yield ProductItem(**card).to_output()
                emitted += 1
        else:

            async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
                product = resolve_url(card["url"]) if card.get("url") else None
                if product is None or product.item_id is None:
                    card["input"] = resolved.url
                    return [ProductItem(**card).to_output()]
                return [item async for item in _product_flow(product, input_model)]

            for batch in await gather_bounded(
                [lambda card=card: load_card(card) for card in cards],
                concurrency=_DETAIL_CONCURRENCY,
            ):
                for item in batch:
                    if "error" not in item and emitted >= cap:
                        return
                    yield item
                    if "error" not in item:
                        emitted += 1
        if emitted >= cap:
            return


_FLOWS = {"product": _product_flow, "listing": _listing_flow}


async def iter_products(
    input_model: WalmartScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield product items for every start URL.

    Each URL is classified and dispatched to its per-kind flow. An unrecognized
    URL yields an ``invalid_url`` error item.
    """
    for url in input_model.startUrls:
        resolved = resolve_url(url)
        if resolved is None:
            yield _error(
                "invalid_url",
                "Start URL was malformed or not a recognized Walmart URL.",
                input_url=url,
            )
            continue
        async for item in _FLOWS[resolved.kind](resolved, input_model):
            yield item


async def scrape_products(
    input_model: WalmartScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_products` into a list, honoring an optional ``limit``."""
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_products(input_model):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="product")
        if limit is not None and len(results) >= limit:
            break
    return results


# --------------------------------------------------------------------------- #
# Reviews flow (deep pagination).                                             #
# --------------------------------------------------------------------------- #


async def _reviews_flow(
    item_id: str, input_model: WalmartReviewsInput
) -> AsyncIterator[dict[str, Any]]:
    """Paginate the public reviews page until empty or ``maxReviews`` reached.

    Walmart does not expose a reliable total up front, so the loop stops on the
    first empty page rather than trusting a page count.
    """
    sort = _REVIEW_SORT[input_model.sort]
    emitted = 0
    for page in range(1, _REVIEWS_PAGE_LIMIT + 1):
        response = await fetch_page(
            _reviews_url(item_id, page, sort), country=input_model.country
        )
        next_data = extract_next_data(response.html) if response else None
        reviews = parse_reviews_page(next_data) if next_data else []
        if not reviews:
            if page == 1 and emitted == 0:
                yield _error(
                    "reviews_not_found",
                    "The product has no public reviews or could not be loaded.",
                    input_url=item_id,
                )
            return
        for raw in reviews:
            raw["usItemId"] = item_id
            raw["input"] = item_id
            yield ReviewItem(**raw).to_output()
            emitted += 1
            if emitted >= input_model.maxReviews:
                return


async def iter_reviews(
    input_model: WalmartReviewsInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield review items for every requested item id (or resolvable URL)."""
    for raw_id in input_model.itemIds:
        item_id = extract_item_id(raw_id)
        if item_id is None:
            yield _error(
                "invalid_url",
                "Could not extract a Walmart item id from the input.",
                input_url=raw_id,
            )
            continue
        async for item in _reviews_flow(item_id, input_model):
            yield item


async def scrape_reviews(
    input_model: WalmartReviewsInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_reviews` into a list, honoring an optional ``limit``."""
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_reviews(input_model):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="review")
        if limit is not None and len(results) >= limit:
            break
    return results
