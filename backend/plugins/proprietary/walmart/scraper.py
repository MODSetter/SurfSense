"""Orchestrate public Walmart product discovery, enrichment, and reviews.

Two streaming cores: :func:`iter_products` dispatches each start URL to a product
or listing flow, and :func:`iter_reviews` paginates the public reviews page per
item id. Network and parsing concerns stay isolated in their own modules so
markup changes and retry policy can be tested independently.

Sources, details, review pages and item ids run side by side through
``ordered_map`` (each page on its own exit, at most 12 pages per call and all
under the transport's one request bound) and still come out in input order.
``WALMART_PARALLEL=0`` runs them one at a time again.

The failure model is in-stream error items (dicts with an ``error`` key), never
exceptions — identical to the Amazon scraper.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator
from contextlib import aclosing, contextmanager
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from proprietary.scraping.concurrency import ordered_map

from .fetch import REVIEWS_HEDGE_S, FetchResult, fetch_page, reporting
from .next_data import extract_next_data
from .parsers import (
    parse_listing_page,
    parse_product,
    parse_reviews_meta,
    parse_reviews_page,
)
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
# Sources and item ids at once; each fans out its own details or review pages.
_SOURCE_CONCURRENCY = 4
_REVIEW_PAGE_CONCURRENCY = 8
# Pages one call has in flight across its sources: one source's fan-out (8
# review pages, or 6 details and the next listing page) is never held back,
# while 4 sources stay well short of 4 x 8.
_CALL_PAGES = 12
_call_slots: ContextVar[asyncio.Semaphore | None] = ContextVar(
    "walmart_call_slots", default=None
)
# Ends a source's stream in _in_order.
_END: Any = object()
_REVIEWS_PER_PAGE = 10
_SEARCH_PAGE_LIMIT = 25  # Walmart caps result pagination at 25 pages.
_REVIEWS_PAGE_LIMIT = 500  # 10 reviews/page → 5000-review safety ceiling.
_DEFAULT_ITEMS_PER_START_URL = 40
# /ip/{slug}/{id}: the URL /ip/{id} redirects to, and the one Walmart links to.
_SLUG_PATH_RE = re.compile(r"^/ip/[^/]+/(\d{4,})$")

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


def _parallel(width: int) -> int:
    """``width``, or 1 when ``WALMART_PARALLEL=0`` turns the fan-out off."""
    return 1 if os.environ.get("WALMART_PARALLEL") == "0" else width


async def _next_data(response: FetchResult | None) -> dict[str, Any] | None:
    """The page's hidden JSON, parsed off the event loop."""
    if response is None:
        return None
    return await asyncio.to_thread(extract_next_data, response.html)


@contextmanager
def _call_bound() -> Iterator[None]:
    """Bound the pages one call has in flight, across all of its sources."""
    token = _call_slots.set(asyncio.Semaphore(_parallel(_CALL_PAGES)))
    try:
        yield
    finally:
        _call_slots.reset(token)


async def _fetch(url: str, **kwargs: Any) -> FetchResult | None:
    """:func:`fetch_page` under the call's bound, when there is one."""
    slots = _call_slots.get()
    if slots is None:
        return await fetch_page(url, **kwargs)
    async with slots:
        return await fetch_page(url, **kwargs)


async def _in_order(
    jobs: Iterable[AsyncIterator[dict[str, Any]]], *, concurrency: int
) -> AsyncIterator[dict[str, Any]]:
    """Run the jobs' streams side by side; yield their items in job order.

    The oldest unfinished job's items go out as they arrive, so the progress
    count moves page by page; the jobs behind it keep theirs until their turn.
    """
    streams = [(job, asyncio.Queue[Any]()) for job in jobs]

    async def pump(
        stream: tuple[AsyncIterator[dict[str, Any]], asyncio.Queue[Any]],
    ) -> None:
        job, queue = stream
        # Closed here when cancelled at a limit, not left for the GC to finalize.
        async with aclosing(job) as items:
            async for item in items:
                queue.put_nowait(item)
        queue.put_nowait(_END)

    async def run() -> None:
        try:
            async with aclosing(
                ordered_map(streams, pump, concurrency=_parallel(concurrency))
            ) as done:
                async for _ in done:
                    pass
        except Exception as exc:
            # The crashed job's stream and every one not yet ended end in it.
            for _, queue in streams:
                queue.put_nowait(exc)

    runner = asyncio.create_task(run())
    try:
        for _, queue in streams:
            while (item := await queue.get()) is not _END:
                if isinstance(item, Exception):
                    raise item
                yield item
    finally:
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)


def _product_url(item_id: str) -> str:
    return f"https://www.walmart.com/ip/{item_id}"


def _detail_url(resolved: ResolvedUrl) -> str:
    """The product page to request for ``resolved``.

    With ``WALMART_CANONICAL_URL=1`` a slug URL is requested as its bare path:
    that is where ``/ip/{id}`` redirects, so asking for it directly saves the
    redirect round trip (about 0.5-1 s) and returns the same page; the query
    (tracking keys such as ``athbdg``) is dropped, as the redirect does. It is
    off by default: in a first live A/B the direct, cookieless hit was sent to
    ``/blocked`` far more often (11 of 26 attempts against 1 of 27 through the
    redirect), so it waits on a proper block-rate gate.
    """
    if not resolved.item_id:
        return resolved.url
    if os.environ.get("WALMART_CANONICAL_URL") == "1":
        match = _SLUG_PATH_RE.match(urlparse(resolved.url).path)
        if match and match.group(1) == resolved.item_id:
            return f"https://www.walmart.com{match.group(0)}"
    return _product_url(resolved.item_id)


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
    response = await _fetch(
        _detail_url(resolved), country=input_model.country, stage="product"
    )
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

    next_data = await _next_data(response)
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


async def _listing_cards(
    url: str, page: int, input_model: WalmartScrapeInput
) -> list[dict[str, Any]]:
    response = await _fetch(
        _page_url(url, page), country=input_model.country, stage="listing"
    )
    next_data = await _next_data(response)
    return parse_listing_page(next_data) if next_data else []


async def _detailed_card(
    card: dict[str, Any], listing_url: str, input_model: WalmartScrapeInput
) -> dict[str, Any]:
    """The card's product page as an item, or the card itself if that fails.

    Either way the item keeps the listing's provenance: ``input`` is the listing
    URL and ``sponsored`` comes from the card, which the product page lacks. A
    failed product page yields the card with a ``detailsError`` note rather than
    an error item, so one blocked page neither loses the product nor costs a
    fetch of the next listing page.
    """
    product = resolve_url(card["url"]) if card.get("url") else None
    items = (
        [item async for item in _product_flow(product, input_model)]
        if product is not None and product.item_id is not None
        else []
    )
    item = next((item for item in items if "error" not in item), None)
    if item is None:
        item = ProductItem(**card).to_output()
        if items:
            item["detailsError"] = (
                f"{items[0]['error']}: {items[0].get('errorDescription') or ''}"
            ).strip()
    elif item.get("sponsored") is None:
        item["sponsored"] = card.get("sponsored")
    item["input"] = listing_url
    return item


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
    # The next listing page, fetched while this page's details are in flight
    # once the cap says it will be needed.
    next_page: asyncio.Task[list[dict[str, Any]]] | None = None
    try:
        for page in range(1, max_pages + 1):
            if next_page is not None:
                cards, next_page = await next_page, None
            else:
                cards = await _listing_cards(resolved.url, page, input_model)
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
            need = max(0, cap - emitted)
            cards = cards[:need]

            if not input_model.includeDetails:
                for card in cards:
                    card["input"] = resolved.url
                    yield ProductItem(**card).to_output()
                    emitted += 1
            else:
                # Every card yields one item (its details or the card itself),
                # so a page short of the cap means the next one is needed. Not
                # with WALMART_PARALLEL=0, which keeps every request serial.
                if len(cards) < need and page < max_pages and _parallel(2) > 1:
                    next_page = asyncio.create_task(
                        _listing_cards(resolved.url, page + 1, input_model)
                    )
                async with aclosing(
                    ordered_map(
                        cards,
                        lambda card: _detailed_card(card, resolved.url, input_model),
                        concurrency=_parallel(_DETAIL_CONCURRENCY),
                    )
                ) as items:
                    async for item in items:
                        yield item
                        emitted += 1
            if emitted >= cap:
                return
    finally:
        if next_page is not None:
            # Awaited, so its exit is released before the flow ends and an
            # error in it is not logged as never retrieved.
            next_page.cancel()
            await asyncio.gather(next_page, return_exceptions=True)


_FLOWS = {"product": _product_flow, "listing": _listing_flow}


async def iter_products(
    input_model: WalmartScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield product items for every start URL.

    Each URL is classified and dispatched to its per-kind flow; the flows run
    side by side and their items come out in start-URL order. An unrecognized
    URL yields an ``invalid_url`` error item.
    """

    async def flow(url: str) -> AsyncIterator[dict[str, Any]]:
        resolved = resolve_url(url)
        if resolved is None:
            yield _error(
                "invalid_url",
                "Start URL was malformed or not a recognized Walmart URL.",
                input_url=url,
            )
            return
        async with aclosing(_FLOWS[resolved.kind](resolved, input_model)) as items:
            async for item in items:
                yield item

    async with aclosing(
        _in_order(map(flow, input_model.startUrls), concurrency=_SOURCE_CONCURRENCY)
    ) as items:
        async for item in items:
            yield item


async def scrape_products(
    input_model: WalmartScrapeInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_products` into a list, honoring an optional ``limit``.

    ``on_item`` hears the count after each item, and ``on_stage`` each page
    fetch's stages, for the caller's progress.
    """
    results: list[dict[str, Any]] = []
    with reporting(on_stage), _call_bound():
        async with aclosing(iter_products(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    return results


# --------------------------------------------------------------------------- #
# Reviews flow (deep pagination).                                             #
# --------------------------------------------------------------------------- #


async def _review_page(
    item_id: str, page: int, input_model: WalmartReviewsInput
) -> tuple[list[dict[str, Any]], int | None]:
    """One reviews page's reviews and the last page its pagination names."""
    response = await _fetch(
        _reviews_url(item_id, page, _REVIEW_SORT[input_model.sort]),
        country=input_model.country,
        stage="reviews",
        hedge_after_s=REVIEWS_HEDGE_S,
    )
    next_data = await _next_data(response)
    if not next_data:
        return [], None
    return parse_reviews_page(next_data), parse_reviews_meta(next_data)["lastPage"]


def _review_pages(first: int, last: int | None, wanted: int, emitted: int) -> range:
    """The next batch of pages to fetch side by side, starting at ``first``.

    Page 1 goes with page 2 when one page cannot fill ``wanted``. Past it, a
    known last page lets the batch cover the reviews still wanted plus one page
    (pages overlap when reviews arrive mid-walk); an unknown one means one page
    at a time, as nothing says how far the reviews go.
    """
    if first == 1:
        return range(1, 3 if wanted > _REVIEWS_PER_PAGE else 2)
    if last is None:
        end = first
    else:
        more = math.ceil((wanted - emitted) / _REVIEWS_PER_PAGE)
        end = min(last, first + more)
    return range(first, min(end, _REVIEWS_PAGE_LIMIT) + 1)


async def _reviews_flow(
    item_id: str, input_model: WalmartReviewsInput
) -> AsyncIterator[dict[str, Any]]:
    """Page through the public reviews until ``maxReviews`` unique reviews.

    Pages are fetched in batches side by side (page 1's pagination says how far
    they go) and read in page order. Stops after the last page the pagination
    names, or at the first empty or failed page. Pages overlap when reviews
    arrive mid-walk (a page's last reviews come back first on the next), so
    repeats are skipped by ``reviewId`` and do not count toward ``maxReviews``.
    With no last page named, a page with nothing new also ends the walk: were
    Walmart to repeat a page past the end, it would otherwise run on, a page at
    a time, to the page limit.
    """
    wanted = input_model.maxReviews
    emitted = 0
    seen: set[str] = set()
    last: int | None = None
    first = 1
    while True:
        pages = _review_pages(first, last, wanted, emitted)
        if not pages:
            return
        async with aclosing(
            ordered_map(
                pages,
                lambda page: _review_page(item_id, page, input_model),
                concurrency=_parallel(_REVIEW_PAGE_CONCURRENCY),
            )
        ) as results:
            page = pages.start
            async for reviews, page_last in results:
                if page == 1:
                    last = page_last
                if not reviews:
                    if page == 1:
                        yield _error(
                            "reviews_not_found",
                            "The product has no public reviews or could not be loaded.",
                            input_url=item_id,
                        )
                    return
                before = emitted
                for raw in reviews:
                    review_id = raw.get("reviewId")
                    if review_id is not None:
                        if review_id in seen:
                            continue
                        seen.add(review_id)
                    raw["usItemId"] = item_id
                    raw["input"] = item_id
                    yield ReviewItem(**raw).to_output()
                    emitted += 1
                    if emitted >= wanted:
                        return
                if last is None and emitted == before:
                    return
                if last is not None and page >= last:
                    return
                page += 1
        first = pages.stop


async def iter_reviews(
    input_model: WalmartReviewsInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield review items for every requested item id (or resolvable URL).

    The ids run side by side; their reviews come out in input order.
    """

    async def flow(raw_id: str) -> AsyncIterator[dict[str, Any]]:
        item_id = extract_item_id(raw_id)
        if item_id is None:
            yield _error(
                "invalid_url",
                "Could not extract a Walmart item id from the input.",
                input_url=raw_id,
            )
            return
        async with aclosing(_reviews_flow(item_id, input_model)) as items:
            async for item in items:
                yield item

    async with aclosing(
        _in_order(map(flow, input_model.itemIds), concurrency=_SOURCE_CONCURRENCY)
    ) as items:
        async for item in items:
            yield item


async def scrape_reviews(
    input_model: WalmartReviewsInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_reviews` into a list, honoring an optional ``limit``.

    ``on_item`` hears the count after each item, and ``on_stage`` each page
    fetch's stages, for the caller's progress.
    """
    results: list[dict[str, Any]] = []
    with reporting(on_stage), _call_bound():
        async with aclosing(iter_reviews(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    return results
