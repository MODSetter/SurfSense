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
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from .fetch import fetch_place_darray, iter_reviews_pages, now_iso, resolve_fid
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
    "imageUrl",
    "neighborhood",
    "street",
    "city",
    "countryCode",
    "postalCode",
    "state",
)


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
    exhausted = True
    filtered = False

    async for raw_page in iter_reviews_pages(fid, sort=sort, language=language):
        stop = False
        for review in parse_reviews_page(raw_page):
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
        if stop:
            exhausted = False
            break

    total = seen if exhausted and not filtered and cutoff is None else None
    return reviews, total


async def _reviews_for_place(
    resolved: ResolvedUrl,
    *,
    input_model: GoogleMapsReviewsInput,
    input_place_id: str | None,
    input_start_url: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """Page one place's reviews and yield a flat ReviewItem per review."""
    fid = await resolve_fid(resolved)
    if not fid:
        logger.warning("[google_maps] reviews: no feature id for %s", resolved.url)
        return

    darray = await fetch_place_darray(fid, language=input_model.language)
    place = parse_place(darray) if darray else {}
    place_header = {k: place[k] for k in _PLACE_KEYS if k in place}
    scraped_at = now_iso()

    reviews, total = await collect_place_reviews(
        place.get("fid", fid),
        max_reviews=input_model.maxReviews,
        sort=input_model.reviewsSort,
        language=input_model.language,
        origin=input_model.reviewsOrigin,
        personal_data=input_model.personalData,
        start_date=input_model.reviewsStartDate,
    )
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
    """Yield Apify-shaped review items for every startUrl and placeId."""
    for entry in input_model.startUrls:
        resolved = resolve_url(entry.url)
        if not resolved:
            logger.warning("Reviews: unrecognized Google Maps URL: %s", entry.url)
            continue
        async for item in _reviews_for_place(
            resolved,
            input_model=input_model,
            input_place_id=None,
            input_start_url=entry.url,
        ):
            yield item

    for place_id in input_model.placeIds:
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        resolved = ResolvedUrl("place", place_id, url)
        async for item in _reviews_for_place(
            resolved,
            input_model=input_model,
            input_place_id=place_id,
            input_start_url=None,
        ):
            yield item


async def scrape_reviews(
    input_model: GoogleMapsReviewsInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_reviews` into a list, honoring an optional guard."""
    results: list[dict[str, Any]] = []
    async for item in iter_reviews(input_model):
        results.append(item)
        if limit is not None and len(results) >= limit:
            break
    return results
