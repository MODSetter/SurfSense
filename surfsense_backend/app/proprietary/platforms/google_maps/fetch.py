"""Proxy-aware fetch seam for the Google Maps scraper.

All network I/O flows through here and always egresses through the residential
proxy (Google blocks datacenter IPs outright; a direct hit also risk-blocks the
server IP). Mirrors the design of ``../youtube/innertube.py`` but trimmed to
what Maps needs today: a GET that returns HTML and a GET that returns the
XSSI-stripped JSON that Maps' internal ``/maps/preview/*`` RPC endpoints emit.

Google Maps place/search/review data is **public** — no Google account is
required. :func:`looks_like_signin_wall` flags the rare responses where Google
serves a consent/sign-in interstitial instead of data, so callers can surface a
clear "sign-in required" error instead of silently returning nothing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

from .parsers import brace_match_json
from .url_resolver import ResolvedUrl, extract_fid

try:  # browser tier is optional (needs patchright browsers installed)
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover - import guard
    StealthyFetcher = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class SignInRequiredError(RuntimeError):
    """Raised when Google serves a sign-in/consent wall instead of public data.

    Public Maps data does not need a Google account, so this is rare; when it
    happens the route surfaces it as a clear "Google sign in required" error
    rather than returning an empty result.
    """


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape Apify stamps on items."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


async def gather_bounded(coro_factories, *, concurrency: int) -> list:
    """Run zero-arg async callables with bounded concurrency, results in order.

    Takes callables (``() -> awaitable``), not live coroutines, so nothing
    starts until a semaphore slot frees up — lets callers queue far more work
    than ``concurrency`` without opening every socket at once. Every RPC here
    is ~2s of proxy round-trip, so overlapping independent ones is the single
    biggest lever on wall-clock time.
    """
    if not coro_factories:
        return []
    sem = asyncio.Semaphore(concurrency)

    async def _run(factory):
        async with sem:
            return await factory()

    return await asyncio.gather(*(_run(f) for f in coro_factories))


# XSSI guard Google prepends to its RPC JSON responses.
_XSSI_PREFIX = ")]}'"

# Consent cookie to dodge the EU consent interstitial that otherwise returns a
# page with no APP_INITIALIZATION_STATE. Mirrors the YouTube fetcher's SOCS.
CONSENT_COOKIES = {
    "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiADGgYIgOa_pgY",
}

_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}


def looks_like_signin_wall(html_or_text: str | None) -> bool:
    """Heuristic: did Google serve a sign-in / consent wall instead of data?

    Public Maps data never needs login, so this should be rare — it mainly
    fires on consent redirects (``consent.google.com``) or an account-picker
    page. Callers turn a True here into a clear "sign-in required" error.
    """
    if not html_or_text:
        return False
    text = html_or_text[:5000].lower()
    markers = (
        "consent.google.com",
        "accounts.google.com/servicelogin",
        "sign in to continue",
        "before you continue to google",
    )
    return any(m in text for m in markers)


def strip_xssi(text: str) -> str:
    """Return the JSON body after Google's ``)]}'`` anti-XSSI guard.

    The guard is normally at position 0, but a proxy/HTML fetcher may wrap the
    text/plain body in ``<html><body><p>…`` — so we locate the guard rather than
    require it at the start, then return everything after its line.
    """
    idx = text.find(_XSSI_PREFIX)
    if idx == -1:
        return text
    nl = text.find("\n", idx)
    return text[nl + 1 :] if nl != -1 else text[idx + len(_XSSI_PREFIX) :]


async def resolve_fid(resolved: ResolvedUrl) -> str | None:
    """Get a place's feature ID: from the URL if present, else from its HTML.

    A ``/maps/place/...`` URL usually embeds the fid in its ``data=`` blob. A
    ``?q=place_id:...`` URL or a shortlink does not, so we fetch the page once
    and pull the fid out of the returned HTML. Raises :class:`SignInRequiredError`
    if Google serves a consent/sign-in wall instead of the page.
    """
    if resolved.fid:
        return resolved.fid
    # Short links (maps.app.goo.gl / goo.gl) are Firebase Dynamic Links: a plain
    # GET only returns a JS interstitial, so render it — the JS follows the
    # redirect to the real /maps/place/… URL, from which we read the fid.
    # ponytail: browser render is slow (~30s) but it's the only way these
    # links resolve; they're rare and cached downstream by fid.
    if resolved.kind == "shortlink":
        rendered = await _fetch_html_stealthy(resolved.url, dict(CONSENT_COOKIES))
        return extract_fid(rendered) if rendered else None
    html = await fetch_html(resolved.url)
    if html is not None:
        if looks_like_signin_wall(html):
            raise SignInRequiredError(
                f"Google returned a sign-in/consent wall for {resolved.url}"
            )
        fid = extract_fid(html)
        if fid:
            return fid
    # Name-only place URLs (e.g. /maps/place/Eiffel+Tower/) serve a JS-only
    # shell whose static HTML never contains the fid (even a headless render
    # won't navigate to the place). The lite ``tbm=map`` search endpoint DOES
    # embed fids in plain HTML, so look the name up there instead.
    if resolved.kind == "place" and resolved.value and resolved.value != resolved.url:
        return await fid_from_search(resolved.value)
    return None


async def fid_from_search(query: str, *, language: str = "en") -> str | None:
    """Resolve a free-text place name to its feature ID via ``tbm=map`` search.

    This is the lite map-search page (the same endpoint the search-discovery
    flow will paginate later); its static HTML embeds every result's fid.
    ``ponytail:`` takes the first fid in the page — that's the top-ranked
    result. Good enough for name lookups; the full search flow will parse the
    structured payload instead.
    """
    url = f"https://www.google.com/search?tbm=map&hl={language}&gl=us&q={quote(query)}"
    html = await fetch_html(url)
    if html is None:
        return None
    if looks_like_signin_wall(html):
        raise SignInRequiredError(
            f"Google returned a sign-in/consent wall for map search {query!r}"
        )
    return extract_fid(html)


async def fetch_html(url: str, *, cookies: dict[str, str] | None = None) -> str | None:
    """GET a Google Maps page and return raw HTML (proxy, stealthy fallback)."""
    merged = {**CONSENT_COOKIES, **(cookies or {})}
    try:
        started = time.perf_counter()
        page = await AsyncFetcher.get(
            url,
            headers=_HEADERS,
            cookies=merged,
            proxy=get_proxy_url(),
            stealthy_headers=True,
        )
        fetch_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[google_maps][perf] source=html url=%s status=%s fetch_ms=%.1f",
            url,
            page.status,
            fetch_ms,
        )
        if page.status == 200:
            return page.html_content
        logger.warning("Maps HTML GET %s returned %s", url, page.status)
    except Exception as e:
        logger.warning("Maps HTML GET %s failed: %s", url, e)
    return await _fetch_html_stealthy(url, merged)


async def _fetch_html_stealthy(url: str, cookies: dict[str, str]) -> str | None:
    """Last-resort browser fetch for anti-bot walls (mirrors the YouTube tier)."""
    if StealthyFetcher is None:
        return None
    try:
        started = time.perf_counter()
        page = await asyncio.to_thread(
            StealthyFetcher.fetch,
            url,
            headless=True,
            network_idle=True,
            solve_cloudflare=True,
            proxy=get_proxy_url(),
        )
        fetch_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[google_maps][perf] source=html tier=stealthy url=%s status=%s fetch_ms=%.1f",
            url,
            page.status,
            fetch_ms,
        )
        if page.status == 200:
            return page.html_content
        logger.warning("Maps HTML GET %s tier=stealthy returned %s", url, page.status)
    except Exception as e:
        logger.warning("Maps HTML GET %s tier=stealthy failed: %s", url, e)
    return None


# Place-detail RPC field selector (protobuf-over-URL). ``{fid}`` is the place's
# feature ID (hex:hex). This is the selector the Maps web app itself sends when
# rendering a place page (captured live via a headless browser, then
# genericized: the free-text ``!2s`` name and per-place ``!15m2…!4s/g/…`` kgmid
# hint dropped with counts adjusted, coords zeroed, and the ``!14m3!1s<EI>``
# session token replaced with a filler — verified the token value is not
# checked). Combined with an NID session cookie it returns the FULL payload:
# reviewsCount, reviews distribution, popular times, image galleries, review
# tags, and every about section. The returned ``jd[6]`` is the ``darray``
# parsers read.
_PLACE_DETAIL_PB = (
    "!1m13!1s{fid}"
    "!3m8!1m3!1d5000!2d0!3d0!3m2!1i1024!2i768!4f13.1"
    "!4m2!3d0!4d0"
    "!12m4!2m3!1i360!2i120!4i8"
    "!13m57!2m2!1i203!2i100!3m2!2i4!5b1"
    "!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
    "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3"
    "!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2"
    "!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
    "!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
    "!14m3!1s0ahUKEwixxxxxxxxxxxxxxxxxxxxxxxxx!7e81!15i10112"
    "!15m108!1m26!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
    "!18m15!3b1!4b1!5b1!6b1!13b1!14b1!17b1!21b1!22b1!30b1!32b1!33m1!1b1!34b1!36e2"
    "!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1"
    "!30m1!2b1!36b1!37b1!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1"
    "!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298"
    "!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1"
    "!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4"
    "!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts"
    "!6m1!1e1!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1!103b1!113b1"
    "!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1!128m1!1b0"
    "!21m0!22m1!1e81!30m8!3b1!6m2!1b1!2b1!7m2!1e3!2b1!9b1"
    "!34m5!7b1!10b1!14b1!15m1!1b0!37i785"
)

# NID session cookie pool. Google trims the rich detail fields (counts,
# distribution, popular times, galleries, tags, most about sections) from
# responses that carry no session cookie; a plain GET to /maps mints an NID
# that unlocks them — no login, no browser. A small pool is rotated
# round-robin (mirrors the YouTube fetcher's ``_RotatingSession``) so no
# single session accumulates the whole request volume; each expires after a
# TTL and is re-minted lazily.
_NID_TTL_S = 30 * 60
_NID_POOL_SIZE = 3
_nid_pool: list[dict[str, Any]] = [
    {"value": None, "at": 0.0} for _ in range(_NID_POOL_SIZE)
]
_nid_rr = 0
_nid_lock = asyncio.Lock()
_nid_inflight: asyncio.Future | None = None


async def _mint_nid() -> str | None:
    """Mint a fresh NID session cookie with a plain GET to /maps."""
    try:
        page = await AsyncFetcher.get(
            "https://www.google.com/maps?hl=en",
            headers=_HEADERS,
            cookies=CONSENT_COOKIES,
            proxy=get_proxy_url(),
            stealthy_headers=True,
        )
        return (page.cookies or {}).get("NID")
    except Exception as e:
        logger.warning("NID mint failed: %s", e)
        return None


async def get_session_cookies() -> dict[str, str]:
    """Consent cookies plus an NID session cookie from the rotating pool.

    Concurrent cold callers coalesce onto a single in-flight mint (the lock is
    not held across the network call), so a burst of parallel detail fetches
    doesn't serialize behind N sequential ~2s mints on a cold pool.
    """
    global _nid_rr, _nid_inflight
    async with _nid_lock:
        slot = _nid_pool[_nid_rr % _NID_POOL_SIZE]
        _nid_rr += 1
        if slot["value"] and time.time() - slot["at"] < _NID_TTL_S:
            return {**CONSENT_COOKIES, "NID": slot["value"]}
        if _nid_inflight is None or _nid_inflight.done():
            _nid_inflight = asyncio.ensure_future(_mint_nid())
        fut = _nid_inflight
    nid = await fut
    if nid:
        async with _nid_lock:
            slot["value"] = nid
            slot["at"] = time.time()
        return {**CONSENT_COOKIES, "NID": nid}
    return dict(CONSENT_COOKIES)


async def fetch_place_darray(fid: str, *, language: str = "en") -> list | None:
    """Fetch a place's detail ``darray`` via the ``/maps/preview/place`` RPC.

    ``fid`` is the feature ID (``0x..:0x..``). Returns ``jd[6]`` (the array all
    place-field paths index into), or ``None`` on failure. Sent with an NID
    session cookie so Google returns the full payload (see ``_PLACE_DETAIL_PB``).
    """
    pb = _PLACE_DETAIL_PB.format(fid=fid)
    url = (
        "https://www.google.com/maps/preview/place"
        f"?authuser=0&hl={language}&gl=us&pb={quote(pb, safe='!')}"
    )
    jd = await fetch_rpc_json(url, cookies=await get_session_cookies())
    darray = jd[6] if isinstance(jd, list) and len(jd) > 6 else None
    return darray if isinstance(darray, list) else None


# Map-search RPC (``search?tbm=map``) field selector. Viewport block first
# (``!1d`` diameter-meters, ``!2d`` lng, ``!3d`` lat), then paging (``!7i``
# per-page, ``!8i`` offset), then the same detail selector blocks the place RPC
# uses so each result embeds a full place darray at ``entry[14]``.
_SEARCH_PB = (
    "!4m12!1m3!1d{diameter}!2d{lng}!3d{lat}"
    "!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1"
    "!7i{per_page}!8i{offset}!10b1"
    "!12m6!1m1!18b1!2m1!20e3!6m1!114b1"
    "!17m1!3e1"
    "!20m57!2m2!1i203!2i100!3m2!2i4!5b1"
    "!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
    "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3"
    "!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2"
    "!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
    "!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
)

# Whole-earth viewport: Google localizes from the query text itself (verified
# live — "pizza new york" returns NYC results with this viewport), so callers
# only need coordinates when the input provides an explicit geolocation.
_EARTH = {"diameter": 25_000_000.0, "lat": 0.0, "lng": 0.0}


def build_search_url(
    query: str,
    *,
    offset: int = 0,
    per_page: int = 20,
    language: str = "en",
    lat: float | None = None,
    lng: float | None = None,
    radius_m: float | None = None,
) -> str:
    """Build a ``search?tbm=map`` URL returning protobuf-over-JSON results."""
    viewport = dict(_EARTH)
    if lat is not None and lng is not None:
        viewport = {
            "diameter": (radius_m or 10_000) * 2,
            "lat": lat,
            "lng": lng,
        }
    pb = _SEARCH_PB.format(per_page=per_page, offset=offset, **viewport)
    return (
        f"https://www.google.com/search?tbm=map&authuser=0&hl={language}&gl=us"
        f"&q={quote(query)}&pb={quote(pb, safe='!')}"
    )


def _search_darrays(jd: Any) -> list[list]:
    """Extract the place darrays from a map-search response.

    Results live at ``jd[0][1]``; each result entry holds its place darray at
    ``entry[14]`` (same shape as the place detail RPC's ``jd[6]``). Multi-result
    pages put metadata (no ``[14]``) in slot 0; single-match responses put the
    one place directly in slot 0 — scanning every entry handles both.
    """
    entries = (
        jd[0][1]
        if isinstance(jd, list) and jd and isinstance(jd[0], list) and len(jd[0]) > 1
        else None
    )
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        darray = entry[14] if isinstance(entry, list) and len(entry) > 14 else None
        if isinstance(darray, list):
            out.append(darray)
    return out


async def iter_search_pages(
    query: str,
    *,
    language: str = "en",
    lat: float | None = None,
    lng: float | None = None,
    radius_m: float | None = None,
    max_pages: int = 25,
    prefetch: int = 1,
):
    """Yield lists of place darrays, one map-search page (~20 places) a time.

    Paging is offset-based (``!8i``); Google reshuffles results between pages
    so callers must dedupe by fid. Stops on an empty page or ``max_pages``.

    ``prefetch`` pages are fetched concurrently per wave (still yielded in
    offset order): each page is a ~2s round-trip, so a caller that knows it
    needs several pages (large ``maxCrawledPlacesPerSearch``) gets them
    overlapped. ``prefetch=1`` keeps the old one-at-a-time behavior for callers
    that only need a page or two (no wasted fetches).
    """
    per_page = 20
    page = 0
    while page < max_pages:
        wave = min(max(prefetch, 1), max_pages - page)
        urls = [
            build_search_url(
                query,
                offset=(page + i) * per_page,
                per_page=per_page,
                language=language,
                lat=lat,
                lng=lng,
                radius_m=radius_m,
            )
            for i in range(wave)
        ]
        pages = await gather_bounded(
            [lambda u=u: fetch_rpc_json(u) for u in urls], concurrency=wave
        )
        for jd in pages:
            darrays = _search_darrays(jd)
            if not darrays:
                return
            yield darrays
        page += wave


# Sort code the reviews RPC expects (slot 1 of the request payload).
REVIEWS_SORT_CODES = {
    "mostRelevant": 1,
    "newest": 2,
    "highestRanking": 3,
    "lowestRanking": 4,
}

# Reviews are cursor-paged (each page's continuation token embeds the previous
# page's last-review key + a signature), so pages CANNOT be fetched in
# parallel — the only lever on review throughput is page size. Google honors
# this on both the first and continuation requests but caps the actual return
# at ~60/page (asking higher just yields the max), so 100 grabs the ceiling and
# cuts the sequential round-trips ~3x vs the old 10/20-per-page default.
_REVIEWS_PAGE_SIZE = 100


def build_reviews_url(
    fid: str, *, sort_code: int, page_token: str = "", language: str = "en"
) -> str:
    """Build a ``GetLocalBoqProxy`` reviews URL (public, no session token).

    This is the review feed the Google search local panel uses. The older
    ``listugcposts`` / ``listentitiesreviews`` RPCs now return empty pages for
    anonymous callers, so this proxy is the one that still works (approach from
    the maintained ``google-maps-review-scraper`` npm package).

    ``fid`` is the feature ID (``0x..:0x..``); ``page_token`` is the opaque
    continuation token from the previous page (empty for the first page).
    """
    inner: list = [None] * 12
    inner[1] = sort_code
    inner[9] = _REVIEWS_PAGE_SIZE
    inner[11] = [fid]
    if page_token:
        inner.extend([None] * 8)
        inner[19] = page_token
    payload = [None, [None] * 9 + [inner]]
    return (
        "https://www.google.com/httpservice/web/PrivateLocalSearchUiDataService/"
        f"GetLocalBoqProxy?msc=gwsrpc&hl={language}"
        f"&reqpld={quote(json.dumps(payload))}"
    )


def _reviews_node(jd: Any) -> list | None:
    """The reviews node of a BOQ response: ``jd[1][10]`` = [.., reviews, .., token]."""
    node = (
        jd[1][10]
        if isinstance(jd, list)
        and len(jd) > 1
        and isinstance(jd[1], list)
        and len(jd[1]) > 10
        else None
    )
    return node if isinstance(node, list) else None


async def iter_reviews_pages(
    fid: str,
    *,
    sort: str = "newest",
    language: str = "en",
    max_pages: int = 10_000,
):
    """Yield raw review arrays, one RPC page (~10 reviews) at a time.

    Each yielded item is the page's review list (``node[2]``). Pagination
    follows ``node[6]`` (the continuation token); stops when it is missing or
    unchanged, or ``max_pages`` is reached. ``ponytail:`` sequential paging —
    the endpoint only hands out one continuation token at a time anyway.
    """
    sort_code = REVIEWS_SORT_CODES.get(sort, 2)
    page_token = ""
    for _ in range(max_pages):
        url = build_reviews_url(
            fid, sort_code=sort_code, page_token=page_token, language=language
        )
        node = _reviews_node(await fetch_rpc_json(url))
        if not node or len(node) < 3 or not isinstance(node[2], list):
            return
        yield node[2]
        next_token = node[6] if len(node) > 6 else None
        if (
            not isinstance(next_token, str)
            or not next_token
            or next_token == page_token
        ):
            return
        page_token = next_token


async def fetch_rpc_json(
    url: str, *, cookies: dict[str, str] | None = None
) -> Any | None:
    """GET a Maps ``/maps/preview/*`` RPC URL and return parsed JSON.

    These endpoints return an XSSI-guarded JSON array (not HTML). Returns the
    decoded structure, or ``None`` on failure / non-JSON (e.g. a sign-in wall).
    """
    try:
        started = time.perf_counter()
        page = await AsyncFetcher.get(
            url,
            headers=_HEADERS,
            cookies=cookies or CONSENT_COOKIES,
            proxy=get_proxy_url(),
            stealthy_headers=True,
        )
        fetch_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[google_maps][perf] source=rpc url=%s status=%s fetch_ms=%.1f",
            url,
            page.status,
            fetch_ms,
        )
        if page.status != 200:
            logger.warning("Maps RPC GET %s returned %s", url, page.status)
            return None
        text = page.html_content
        if looks_like_signin_wall(text):
            logger.warning("Maps RPC GET %s hit a sign-in/consent wall", url)
            return None
        # brace_match_json is a pure-Python scan and review payloads reach
        # ~1MB; decode off-loop so it can't stall concurrent requests.
        return await asyncio.to_thread(_decode_rpc_body, text)
    except Exception as e:
        logger.warning("Maps RPC GET %s failed: %s", url, e)
        return None


def _decode_rpc_body(text: str) -> Any | None:
    """Strip the XSSI guard and decode the balanced top-level JSON blob."""
    body = strip_xssi(text)
    # The proxy/HTML fetcher may wrap the JSON in <html><body><p>…</p>…,
    # so extract just the balanced top-level array/object.
    start = next((i for i, c in enumerate(body) if c in "[{"), -1)
    if start == -1:
        return None
    blob = brace_match_json(body, start)
    return json.loads(blob) if blob else None
