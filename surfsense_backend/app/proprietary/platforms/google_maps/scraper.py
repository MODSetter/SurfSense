"""Orchestrator for the Google Maps places scraper (Apify-compatible).

Skeleton mirroring the YouTube scraper layout: the core is the async generator
:func:`iter_places` (unbounded), :func:`scrape_places` is a thin collector with
a caller-supplied ``limit`` guard. Discovery inputs dispatch to per-kind flows
(search / place URL / place ID) which are currently no-ops — each will be
implemented progressively, exactly like the YouTube flows were.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from .fetch import (
    SignInRequiredError,
    fetch_place_darray,
    gather_bounded,
    iter_search_pages,
    now_iso,
    resolve_fid,
)
from .parsers import parse_place
from .schemas import GoogleMapsScrapeInput, PlaceItem
from .url_resolver import ResolvedUrl, resolve_url

logger = logging.getLogger(__name__)

# Re-exported so callers/routes can keep importing it from the orchestrator.
__all__ = ["SignInRequiredError", "iter_places", "scrape_places"]

# Max concurrent per-place detail/review fetches. Each is a ~2s proxy
# round-trip, so overlapping them is what turns a 20-place enriched search from
# ~50s into a handful of seconds. ``ponytail:`` a fixed ceiling — high enough to
# hide latency, low enough not to trip Google/proxy rate limits; make it
# configurable if a faster proxy pool ever wants more.
_DETAIL_CONCURRENCY = 8

_SEARCH_PAGE_SIZE = 20


def _prefetch_for(cap: int | None) -> int:
    """How many search pages to fetch per wave, from the result cap.

    One page holds ~20 results, so a cap of 60 wants ~3 pages overlapped; an
    uncapped scan overlaps a small fixed wave. Capped at 5 to bound wasted
    fetches when dedupe or an early empty page cuts things short.
    """
    if cap is None:
        return 5
    return max(1, min(5, (cap + _SEARCH_PAGE_SIZE - 1) // _SEARCH_PAGE_SIZE))


# Apify's placeMinimumStars options -> numeric cutoff.
_MIN_STARS = {
    "two": 2.0,
    "twoAndHalf": 2.5,
    "three": 3.0,
    "threeAndHalf": 3.5,
    "four": 4.0,
    "fourAndHalf": 4.5,
}


def _location_text(input_model: GoogleMapsScrapeInput) -> str | None:
    """The location to scope searches to (Apify appends it to the query)."""
    if input_model.locationQuery:
        return input_model.locationQuery
    parts = [
        input_model.city,
        input_model.county,
        input_model.state,
        input_model.postalCode,
        input_model.countryCode,
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _custom_point(
    input_model: GoogleMapsScrapeInput,
) -> tuple[float | None, float | None, float | None]:
    """(lat, lng, radius_m) from a GeoJSON-ish customGeolocation Point."""
    geo = input_model.customGeolocation
    if not isinstance(geo, dict) or geo.get("type") != "Point":
        return None, None, None
    coords = geo.get("coordinates")
    if not isinstance(coords, list | tuple) or len(coords) < 2:
        return None, None, None
    lng, lat = coords[0], coords[1]
    radius_km = geo.get("radiusKm") or geo.get("radius") or 10
    return float(lat), float(lng), float(radius_km) * 1000


def _passes_filters(
    fields: dict[str, Any], query: str, input_model: GoogleMapsScrapeInput
) -> bool:
    """Apply Apify's search result filters to parsed place fields."""
    title = (fields.get("title") or "").lower()
    q = query.lower()
    if input_model.searchMatching == "only_exact" and title != q:
        return False
    if input_model.searchMatching == "only_includes" and q not in title:
        return False

    if input_model.categoryFilterWords:
        cats = " ".join(fields.get("categories") or []).lower()
        if not any(w.lower() in cats for w in input_model.categoryFilterWords):
            return False

    min_stars = _MIN_STARS.get(input_model.placeMinimumStars)
    if min_stars is not None and (fields.get("totalScore") or 0) < min_stars:
        return False

    if input_model.website == "withWebsite" and not fields.get("website"):
        return False
    if input_model.website == "withoutWebsite" and fields.get("website"):
        return False

    return not (
        input_model.skipClosedPlaces
        and (fields.get("permanentlyClosed") or fields.get("temporarilyClosed"))
    )


def _apply_image_cap(
    fields: dict[str, Any], input_model: GoogleMapsScrapeInput
) -> None:
    """Apify semantics: gallery ``imageUrls`` only when ``maxImages > 0``."""
    if not input_model.maxImages:
        fields.pop("imageUrls", None)
    elif "imageUrls" in fields:
        fields["imageUrls"] = fields["imageUrls"][: input_model.maxImages]


async def _enrich_from_detail(
    fields: dict[str, Any], input_model: GoogleMapsScrapeInput
) -> dict[str, Any]:
    """Merge the full detail-RPC payload over search-result fields.

    Search darrays are served without the session-gated extras (reviewsCount,
    distribution, popular times, galleries, tags, full about sections); the
    detail RPC with an NID cookie has them all. Detail values win on overlap.
    """
    fid = fields.get("fid")
    if not fid:
        return fields
    darray = await fetch_place_darray(fid, language=input_model.language)
    if not darray:
        return fields
    return {**fields, **parse_place(darray)}


async def _build_items(
    candidates: list[tuple[dict[str, Any], str, int]],
    input_model: GoogleMapsScrapeInput,
    *,
    search_string: str,
    search_page_url: str | None,
    enrich: bool,
) -> list[dict[str, Any]]:
    """Turn dedup'd/filtered place fields into output items, in parallel.

    Each candidate is ``(fields, fid, rank)``. Detail enrichment and inline
    reviews are per-place round-trips; running the whole batch concurrently
    (bounded, order preserved) is the main speedup over the old one-at-a-time
    loop. Pure-CPU when neither enrichment nor reviews are requested.
    """

    async def _build(fields: dict[str, Any], fid: str, rank: int) -> dict[str, Any]:
        if enrich:
            fields = await _enrich_from_detail(fields, input_model)
        _apply_image_cap(fields, input_model)
        item = PlaceItem(**fields)
        item.searchString = search_string
        if search_page_url:
            item.searchPageUrl = search_page_url
        item.rank = rank
        item.url = (
            f"https://www.google.com/maps/place/?q=place_id:{fields.get('placeId')}"
        )
        item.scrapedAt = now_iso()
        if input_model.maxReviews:
            await _attach_reviews(item, fid, input_model)
        return item.to_output()

    return await gather_bounded(
        [lambda c=c: _build(*c) for c in candidates],
        concurrency=_DETAIL_CONCURRENCY,
    )


async def _search_flow(
    query: str, *, input_model: GoogleMapsScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Search-term discovery via the ``search?tbm=map`` RPC.

    Pages offset-based results (~20/page), dedupes by fid (Google reshuffles
    between pages), applies the Apify filters, and emits full place items —
    each search hit already carries a place darray, so no per-place request is
    needed for the core fields. When ``scrapePlaceDetailPage`` or ``maxImages``
    is set, one detail RPC per place adds the session-gated extras; those are
    fetched concurrently across the page rather than one at a time.
    """
    location = _location_text(input_model)
    search_query = f"{query} in {location}" if location else query
    lat, lng, radius_m = _custom_point(input_model)
    cap = input_model.maxCrawledPlacesPerSearch
    enrich = bool(input_model.scrapePlaceDetailPage or input_model.maxImages)
    search_page_url = (
        f"https://www.google.com/maps/search/{quote(search_query, safe='')}"
    )

    seen: set[str] = set()
    emitted = 0
    async for darrays in iter_search_pages(
        search_query,
        language=input_model.language,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        prefetch=_prefetch_for(cap),
    ):
        candidates: list[tuple[dict[str, Any], str, int]] = []
        new_on_page = 0
        for darray in darrays:
            fields = parse_place(darray)
            fid = fields.get("fid")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            new_on_page += 1
            if _passes_filters(fields, query, input_model):
                candidates.append((fields, fid, len(seen)))
        if cap is not None:
            candidates = candidates[: max(0, cap - emitted)]
        for out in await _build_items(
            candidates,
            input_model,
            search_string=query,
            search_page_url=search_page_url,
            enrich=enrich,
        ):
            yield out
            emitted += 1
        if cap is not None and emitted >= cap:
            return
        if not new_on_page:  # page was all repeats -> feed is cycling, stop
            return


# Broad category sweep for allPlacesNoSearchAction. Apify's implementation
# OCRs / mouse-overs the rendered map pins (hence the enum names); the public
# search RPC has no "list everything" query (verified: '*' and '' return
# nothing). ponytail: approximate the scan with broad category searches over
# the same viewport, deduped by fid — covers the vast majority of pins; a true
# pin-complete scan would need browser rendering + tile OCR.
_ALL_PLACES_SWEEP = [
    "restaurant",
    "cafe",
    "bar",
    "store",
    "shopping",
    "hotel",
    "tourist attraction",
    "park",
    "gym",
    "salon",
    "bank",
    "gas station",
    "pharmacy",
    "doctor",
    "school",
    "church",
    "services",
]


async def _all_places_flow(
    input_model: GoogleMapsScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Area scan without a search term: sweep broad categories, dedupe by fid.

    Emits the same items the search flow would; ``searchString`` carries the
    action value so callers can tell scan hits from query hits.
    """
    location = _location_text(input_model)
    lat, lng, radius_m = _custom_point(input_model)
    cap = input_model.maxCrawledPlacesPerSearch
    enrich = bool(input_model.scrapePlaceDetailPage or input_model.maxImages)
    seen: set[str] = set()
    emitted = 0
    for term in _ALL_PLACES_SWEEP:
        search_query = f"{term} in {location}" if location else term
        async for darrays in iter_search_pages(
            search_query,
            language=input_model.language,
            lat=lat,
            lng=lng,
            radius_m=radius_m,
            prefetch=_prefetch_for(cap),
        ):
            candidates: list[tuple[dict[str, Any], str, int]] = []
            new_on_page = 0
            for darray in darrays:
                fields = parse_place(darray)
                fid = fields.get("fid")
                if not fid or fid in seen:
                    continue
                seen.add(fid)
                new_on_page += 1
                if _passes_filters(fields, "", input_model):
                    candidates.append((fields, fid, len(seen)))
            if cap is not None:
                candidates = candidates[: max(0, cap - emitted)]
            for out in await _build_items(
                candidates,
                input_model,
                search_string=input_model.allPlacesNoSearchAction,
                search_page_url=None,
                enrich=enrich,
            ):
                yield out
                emitted += 1
            if cap is not None and emitted >= cap:
                return
            if not new_on_page:
                break  # this term is exhausted; move to the next one


async def _place_flow(
    resolved: ResolvedUrl, *, input_model: GoogleMapsScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Single place from a direct Maps place URL / place ID.

    Resolves the feature ID, fetches the place detail via the ``/maps/preview/
    place`` RPC (full payload — see ``_PLACE_DETAIL_PB``), and maps the fields
    into a ``PlaceItem``. When ``maxReviews > 0`` the place's reviews are
    attached inline (Apify puts them on ``reviews[]``).
    """
    fid = await resolve_fid(resolved)
    if not fid:
        logger.warning("[google_maps] could not resolve feature id: %s", resolved.url)
        return
    darray = await fetch_place_darray(fid, language=input_model.language)
    if not darray:
        logger.warning(
            "[google_maps] no place data (structure may have shifted): %s", resolved.url
        )
        return
    fields = parse_place(darray)
    _apply_image_cap(fields, input_model)
    item = PlaceItem(**fields)
    item.url = resolved.url
    item.searchString = f"Direct URL: {resolved.url}"
    item.scrapedAt = now_iso()
    if input_model.maxReviews and fields.get("fid"):
        await _attach_reviews(item, fields["fid"], input_model)
    yield item.to_output()


async def _attach_reviews(
    item: PlaceItem, fid: str, input_model: GoogleMapsScrapeInput
) -> None:
    """Populate ``item.reviews`` (and total count when knowable) from the feed."""
    from .reviews import collect_place_reviews

    reviews, total = await collect_place_reviews(
        fid,
        max_reviews=input_model.maxReviews,
        sort=input_model.reviewsSort,
        language=input_model.language,
        filter_string=input_model.reviewsFilterString,
        origin=input_model.reviewsOrigin,
        personal_data=input_model.scrapeReviewsPersonalData,
        start_date=input_model.reviewsStartDate,
    )
    item.reviews = reviews
    if total is not None and item.reviewsCount is None:
        item.reviewsCount = total


async def _place_id_flow(
    place_id: str, *, input_model: GoogleMapsScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Single place from a bare place ID (format ``ChIJ...``).

    Maps resolves ``?q=place_id:<id>`` to the place page, so we build that URL
    and reuse the place flow.
    """
    url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    resolved = ResolvedUrl("place", place_id, url)
    async for item in _place_flow(resolved, input_model=input_model):
        yield item


async def _dispatch(
    resolved: ResolvedUrl, input_model: GoogleMapsScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    if resolved.kind == "search":
        async for item in _search_flow(resolved.value, input_model=input_model):
            yield item
    else:  # place / cid / shortlink / reviews all resolve to a place page
        async for item in _place_flow(resolved, input_model=input_model):
            yield item


async def iter_places(
    input_model: GoogleMapsScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield Apify-shaped place items from all discovery inputs.

    Apify runs searches, startUrls, and placeIds side by side (they are
    additive, unlike the YouTube scraper where startUrls override queries).
    """
    for entry in input_model.startUrls:
        resolved = resolve_url(entry.url)
        if not resolved:
            logger.warning("Unrecognized Google Maps URL: %s", entry.url)
            continue
        async for item in _dispatch(resolved, input_model):
            yield item

    # placeIds are independent single-place detail fetches (~2s each); run the
    # batch concurrently, bounded, results in input order — a bulk list of IDs
    # is the common case and was previously fully sequential.
    if input_model.placeIds:

        async def _collect(pid: str) -> list[dict[str, Any]]:
            return [it async for it in _place_id_flow(pid, input_model=input_model)]

        for items in await gather_bounded(
            [lambda p=p: _collect(p) for p in input_model.placeIds],
            concurrency=_DETAIL_CONCURRENCY,
        ):
            for item in items:
                yield item

    for query in input_model.searchStringsArray:
        async for item in _search_flow(query, input_model=input_model):
            yield item

    if input_model.allPlacesNoSearchAction:
        async for item in _all_places_flow(input_model):
            yield item


async def scrape_places(
    input_model: GoogleMapsScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_places` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route), NOT a ceiling
    in the streaming core.
    """
    results: list[dict[str, Any]] = []
    async for item in iter_places(input_model):
        results.append(item)
        if limit is not None and len(results) >= limit:
            break
    return results
