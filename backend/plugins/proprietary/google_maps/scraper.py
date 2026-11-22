"""Orchestrator for the Google Maps places scraper (Apify-compatible).

Skeleton mirroring the YouTube scraper layout: the core is the async generator
:func:`iter_places` (unbounded), :func:`scrape_places` is a thin collector with
a caller-supplied ``limit`` guard. Discovery inputs dispatch to per-kind flows
(search / place URL / place ID) which are currently no-ops — each will be
implemented progressively, exactly like the YouTube flows were.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from typing import Any
from urllib.parse import quote

from proprietary.scraping.concurrency import ordered_map
from proprietary.scraping.logged_host import logged_host

from .fetch import (
    GoogleRefusedError,
    SignInRequiredError,
    call_bound,
    error_item,
    fetch_place_darray,
    iter_search_pages,
    job_session,
    now_iso,
    reporting,
    resolve_fid,
    together,
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
# configurable if a faster proxy pool ever wants more. It matches the job
# session's 8 streams: a place that fetches both its detail and its reviews
# holds two, so half as many places run then, or requests would queue for a
# stream past the hedge delay and hedges would fire on queueing, not slow exits.
_DETAIL_CONCURRENCY = 8

# Sources (URLs, place IDs, searches) scraped at once (GMP-5): each on its own
# exit, so the rate each IP sees is unchanged.
_SOURCE_CONCURRENCY = 6

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
    detail RPC has them all. Detail values win on overlap.
    """
    fid = fields.get("fid")
    if not fid:
        return fields
    try:
        darray = await fetch_place_darray(fid, language=input_model.language)
    except GoogleRefusedError as error:
        # One refused place keeps its search fields; the search keeps the rest.
        logger.warning("[google_maps] a place's detail was refused: %s", error)
        return fields
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
        fetched = None
        if enrich and input_model.maxReviews:
            # Both need only the fid: send them together, not one after the other.
            fields, fetched = await together(
                _enrich_from_detail(fields, input_model),
                _place_reviews(fid, input_model),
            )
        elif enrich:
            fields = await _enrich_from_detail(fields, input_model)
        elif input_model.maxReviews:
            fetched = await _place_reviews(fid, input_model)
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
        if fetched is not None:
            _attach_reviews(item, fetched)
        return item.to_output()

    per_place = 2 if enrich and input_model.maxReviews else 1
    async with aclosing(
        ordered_map(
            candidates,
            lambda c: _build(*c),
            concurrency=max(1, _DETAIL_CONCURRENCY // per_place),
        )
    ) as items:
        return [item async for item in items]


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
    # aclosing: an early return cancels the wave's page fetches still in flight
    # while the job's session is open, not later in the garbage collector.
    pages = iter_search_pages(
        search_query,
        language=input_model.language,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        prefetch=_prefetch_for(cap),
    )
    async with aclosing(pages):
        async for darrays in pages:
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
        pages = iter_search_pages(
            search_query,
            language=input_model.language,
            lat=lat,
            lng=lng,
            radius_m=radius_m,
            prefetch=_prefetch_for(cap),
        )
        async with aclosing(pages):
            async for darrays in pages:
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
    fid = await resolve_fid(resolved, language=input_model.language)
    if not fid:
        logger.warning(
            "[google_maps] could not resolve the feature id of a %s link", resolved.kind
        )
        return
    fetched = None
    if input_model.maxReviews:
        # The detail and the reviews need only the fid: fetch them together.
        darray, fetched = await together(
            fetch_place_darray(fid, language=input_model.language),
            _place_reviews(fid, input_model),
        )
    else:
        darray = await fetch_place_darray(fid, language=input_model.language)
    if not darray:
        logger.warning(
            "[google_maps] no place data for a %s link (structure may have shifted)",
            resolved.kind,
        )
        return
    fields = parse_place(darray)
    _apply_image_cap(fields, input_model)
    item = PlaceItem(**fields)
    item.url = resolved.url
    item.searchString = f"Direct URL: {resolved.url}"
    item.scrapedAt = now_iso()
    if fetched is not None:
        _attach_reviews(item, fetched)
    yield item.to_output()


async def _place_reviews(
    fid: str, input_model: GoogleMapsScrapeInput
) -> tuple[list[dict[str, Any]], int | None]:
    """A place's reviews from the feed, as ``(reviews, exact_total_or_None)``.

    A feed refused on every exit costs the place its reviews, not the place.
    """
    from .reviews import collect_place_reviews

    try:
        return await collect_place_reviews(
            fid,
            max_reviews=input_model.maxReviews,
            sort=input_model.reviewsSort,
            language=input_model.language,
            filter_string=input_model.reviewsFilterString,
            origin=input_model.reviewsOrigin,
            personal_data=input_model.scrapeReviewsPersonalData,
            start_date=input_model.reviewsStartDate,
        )
    except GoogleRefusedError as error:
        logger.warning("[google_maps] a place's reviews were refused: %s", error)
        return [], None


def _attach_reviews(
    item: PlaceItem, fetched: tuple[list[dict[str, Any]], int | None]
) -> None:
    """Populate ``item.reviews`` (and total count when knowable)."""
    reviews, total = fetched
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
    So do we: each source is one job on its own session, the jobs run at once
    and their items come out in input order (startUrls, placeIds, searches,
    then the allPlacesNoSearchAction sweep).
    A source that fails on every exit becomes one error item naming it.
    """
    jobs: list[tuple[str, AsyncIterator[dict[str, Any]]]] = []
    for entry in input_model.startUrls:
        resolved = resolve_url(entry.url)
        if not resolved:
            logger.warning("Unrecognized Google Maps URL on %s", logged_host(entry.url))
            continue
        jobs.append((entry.url, _dispatch(resolved, input_model)))
    for pid in input_model.placeIds:
        jobs.append((pid, _place_id_flow(pid, input_model=input_model)))
    for query in input_model.searchStringsArray:
        jobs.append((query, _search_flow(query, input_model=input_model)))
    if input_model.allPlacesNoSearchAction:
        action = input_model.allPlacesNoSearchAction
        jobs.append((action, _all_places_flow(input_model)))

    async def run(job: tuple[str, AsyncIterator[dict[str, Any]]]) -> list[dict]:
        source, flow = job
        try:
            async with job_session(), aclosing(flow):
                return [item async for item in flow]
        except GoogleRefusedError as error:
            logger.warning("[google_maps] a source failed: %s", error)
            return [error_item(error, source)]

    async with aclosing(
        ordered_map(jobs, run, concurrency=_SOURCE_CONCURRENCY)
    ) as results:
        async for items in results:
            for item in items:
                yield item


async def scrape_places(
    input_model: GoogleMapsScrapeInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_places` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route), NOT a ceiling
    in the streaming core. ``on_item`` hears the count after each item and
    ``on_stage`` each stage of the call (a page fetched, a retry), for the
    caller's progress.
    """
    results: list[dict[str, Any]] = []
    with reporting(on_stage), call_bound():
        async with aclosing(iter_places(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    return results
