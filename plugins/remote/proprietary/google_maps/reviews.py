"""Orchestrator for the Google Maps Reviews scraper (Apify-compatible).

Distinct from the places scraper: one flat output item per review (the review
fields merged with the parent place fields), per the Apify "Google Maps Reviews
Scraper" output schema.

Reviews come from Google's public ``GetLocalBoqProxy`` review feed (no login,
~10 reviews per page, opaque continuation-token pagination). The place header
fields stamped onto each item come from the same ``/maps/preview/place`` RPC the
places scraper uses.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from datetime import datetime
from typing import Any

from proprietary.scraping.concurrency import ordered_map

from .fetch import (
    GoogleRefusedError,
    call_bound,
    error_item,
    fetch_place_darray,
    iter_reviews_pages,
    job_session,
    now_iso,
    report,
    reporting,
    resolve_place,
    together,
)
from .parsers import parse_place, parse_reviews_page, strip_personal_data
from .schemas import GoogleMapsReviewsInput, ReviewItem
from .url_resolver import ResolvedUrl, resolve_url

logger = logging.getLogger(__name__)

# Place header keys copied from a parsed place onto every ReviewItem.
_PLACE_KEYS = (
    "title",
    "placeId",
    "address",
    "location",
    "categories",
    "categoryName",
    "totalScore",
    "reviewsCount",
    "price",
    "cid",
    "fid",
    "kgmid",
    "imageUrl",
    "neighborhood",
    "street",
    "city",
    "countryCode",
    "postalCode",
    "state",
)

# Places whose reviews are read at once (GMP-5): each on its own exit, so the
# rate each IP sees is unchanged.
_SOURCE_CONCURRENCY = 6


def _parse_start_date(value: str | None) -> datetime | None:
    """Parse ``reviewsStartDate`` (ISO date/datetime) into a UTC-naive cutoff."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        logger.warning("[google_maps] bad reviewsStartDate: %r", value)
        return None


def _before_cutoff(review: dict[str, Any], cutoff: datetime) -> bool:
    """True if a review predates the cutoff (newest-first stop condition)."""
    iso = review.get("publishedAtDate")
    if not iso:
        return False
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return False
    return when < cutoff


def _keep(review: dict[str, Any], *, filter_string: str, origin: str) -> bool:
    """Apply Apify's reviewsFilterString / reviewsOrigin filters client-side."""
    if origin == "google" and (review.get("reviewOrigin") or "Google") != "Google":
        return False
    if filter_string:
        text = (review.get("text") or "") + " " + (review.get("textTranslated") or "")
        if filter_string.lower() not in text.lower():
            return False
    return True


async def collect_place_reviews(
    fid: str,
    *,
    max_reviews: int,
    sort: str = "newest",
    language: str = "en",
    filter_string: str = "",
    origin: str = "all",
    personal_data: bool = True,
    start_date: str | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """Page a place's reviews via the BOQ feed.

    Returns ``(reviews, exact_total_or_None)``. The feed does not expose the
    place's total review count up front, so the total is only known when
    pagination exhausts before ``max_reviews`` is hit (and no filters dropped
    anything) — the common case for small/medium places.
    """
    cutoff = _parse_start_date(start_date)
    reviews: list[dict[str, Any]] = []
    seen = 0
    pages = 0
    exhausted = True
    filtered = False

    try:
        async for raw_page in iter_reviews_pages(fid, sort=sort, language=language):
            pages += 1
            stop = False
            for review in parse_reviews_page(raw_page, language):
                seen += 1
                if cutoff and _before_cutoff(review, cutoff):
                    stop = True
                    break
                if not _keep(review, filter_string=filter_string, origin=origin):
                    filtered = True
                    continue
                if not personal_data:
                    strip_personal_data(review)
                reviews.append(review)
                if len(reviews) >= max_reviews:
                    stop = True
                    break
            await report(f"{len(reviews)} reviews read")
            if stop:
                exhausted = False
                break
    except GoogleRefusedError as error:
        if not pages:
            raise
        # A later page refused on every exit costs its reviews, not the pages
        # already read.
        logger.warning("[google_maps] reviews of %s cut short: %s", fid, error)
        exhausted = False

    total = seen if exhausted and not filtered and cutoff is None else None
    return reviews, total


async def _header_darray(fid: str, *, language: str) -> list | None:
    """The place's detail for the review header; refused, the reviews go bare."""
    try:
        return await fetch_place_darray(fid, language=language)
    except GoogleRefusedError as error:
        logger.warning("[google_maps] header of %s: %s", fid, error)
        return None


async def _reviews_for_place(
    resolved: ResolvedUrl,
    *,
    input_model: GoogleMapsReviewsInput,
    input_place_id: str | None,
    input_start_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """Page one place's reviews and yield a flat ReviewItem per review."""
    fid, darray = await resolve_place(resolved, language=input_model.language)
    if not fid:
        logger.warning("[google_maps] reviews: no feature id for %s", resolved.url)
        return

    scraped_at = now_iso()
    collecting = collect_place_reviews(
        fid,
        max_reviews=input_model.maxReviews,
        sort=input_model.reviewsSort,
        language=input_model.language,
        origin=input_model.reviewsOrigin,
        personal_data=input_model.personalData,
        start_date=input_model.reviewsStartDate,
    )
    if darray is None:
        # The header and the reviews need only the fid: ask for both at once,
        # as the Maps web app does, rather than one after the other.
        darray, (reviews, total) = await together(
            _header_darray(fid, language=input_model.language), collecting
        )
    else:  # a name lookup already brought the place's search darray
        reviews, total = await collecting
    place = parse_place(darray) if darray else {}
    place_header = {k: place[k] for k in _PLACE_KEYS if k in place}
    if total is not None and "reviewsCount" not in place_header:
        place_header["reviewsCount"] = total

    for review in reviews:
        item = ReviewItem(**{**place_header, **review})
        item.scrapedAt = scraped_at
        item.language = input_model.language
        item.inputPlaceId = input_place_id
        item.inputStartUrl = input_start_url
        item.url = place.get("url") or resolved.url
        yield item.to_output()


async def iter_reviews(
    input_model: GoogleMapsReviewsInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield Apify-shaped review items for every startUrl and placeId.

    The places are read side by side, each on its own session, and their items
    come out in input order. A place that fails on every exit becomes one
    error item naming it.
    """
    jobs: list[tuple[ResolvedUrl, str | None, str | None]] = []
    for entry in input_model.startUrls:
        resolved = resolve_url(entry.url)
        if not resolved:
            logger.warning("Reviews: unrecognized Google Maps URL: %s", entry.url)
            continue
        jobs.append((resolved, None, entry.url))
    for place_id in input_model.placeIds:
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        jobs.append((ResolvedUrl("place", place_id, url), place_id, None))

    async def run(job: tuple[ResolvedUrl, str | None, str | None]) -> list[dict]:
        resolved, place_id, start_url = job
        try:
            async with job_session():
                return [
                    item
                    async for item in _reviews_for_place(
                        resolved,
                        input_model=input_model,
                        input_place_id=place_id,
                        input_start_url=start_url,
                    )
                ]
        except GoogleRefusedError as error:
            logger.warning("[google_maps] reviews of %s: %s", resolved.url, error)
            return [error_item(error, place_id or start_url or resolved.url)]

    async with aclosing(
        ordered_map(jobs, run, concurrency=_SOURCE_CONCURRENCY)
    ) as results:
        async for items in results:
            for item in items:
                yield item


async def scrape_reviews(
    input_model: GoogleMapsReviewsInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_reviews` into a list, honoring an optional guard.

    ``on_item`` hears the count after each item and ``on_stage`` each stage of
    the call (a page fetched, a retry), for the caller's progress.
    """
    results: list[dict[str, Any]] = []
    with reporting(on_stage), call_bound():
        async with aclosing(iter_reviews(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    return results
