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
import os
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterator
from contextlib import aclosing, asynccontextmanager, contextmanager, nullcontext
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged, ordered_map
from proprietary.scraping.proxy import get_proxy_url

from .parsers import _reviews_tags, brace_match_json, dig
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


class GoogleRefusedError(RuntimeError):
    """Google refused a request, or never answered it, on every exit tried.

    A refusal is a 403, a 429 or a sorry page. Callers turn the error into an
    item naming the input, so one refused place does not cost the call the
    others.
    """


def error_item(error: Exception, source: str) -> dict[str, Any]:
    """The item that stands for a source that failed on every exit, naming it."""
    return {"error": str(error), "input": source}


_PLUGIN = "google-maps"

# Payloads are 200 KB or less and come back in 3.4 s or less, so a dead exit
# is dropped after 5 s to connect or 15 s in all, not Scrapling's 30 s (GMP-1).
_TIMEOUT = (5, 10)

# The first try and two rotations to a fresh exit (GMP-7).
_ATTEMPTS = 3

# A request still unanswered after this long is sent again on a fresh exit and
# the first answer wins (GMP-8); 0 turns hedging off.
_HEDGE_AFTER_S = float(os.getenv("GOOGLE_MAPS_HEDGE_AFTER_S", "2.5"))
# A 100-review page takes 1.6-2.0 s alone and 2-4 s when 8 streams share one
# exit, so a reviews request is only slow well past the other stages' delay;
# 0 turns hedging off for reviews alone.
_REVIEWS_HEDGE_AFTER_S = float(os.getenv("GOOGLE_MAPS_REVIEWS_HEDGE_AFTER_S", "4"))

# One keep-alive session per place or search job (GMP-7): every request after
# the first skips the proxy CONNECT and TLS. GOOGLE_MAPS_KEEP_ALIVE=0 sends each
# request on its own fresh exit, as before. GOOGLE_MAPS_KEEP_IDLE=1 also lends a
# job's warm session to the next call (GMP-10); off until prod shows no blocks.
_KEEP_ALIVE = os.getenv("GOOGLE_MAPS_KEEP_ALIVE", "1") != "0"
_KEEP_IDLE = os.getenv("GOOGLE_MAPS_KEEP_IDLE", "0") == "1"
_MAX_USES = 30
_MAX_STREAMS = 8

# Requests one tool call has in flight across all its sources, hedges aside: 6
# sources of 8 streams would take the host's whole SCRAPING_MAX_HTTP by themselves
# and queue every other call behind this one.
_CALL_MAX_IN_FLIGHT = 16
_call_slots: ContextVar[asyncio.Semaphore | None] = ContextVar(
    "google_maps_call_slots", default=None
)

# The tool's progress reporter for this call, inherited by the tasks it starts,
# so the flows report stage boundaries without threading it through each call.
_reporter: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "google_maps_reporter", default=None
)


@contextmanager
def reporting(hear: Callable[[str], Awaitable[None]] | None) -> Iterator[None]:
    """Send the stage messages of the block (and its tasks) to ``hear``."""
    token = _reporter.set(hear)
    try:
        yield
    finally:
        _reporter.reset(token)


@contextmanager
def call_bound() -> Iterator[None]:
    """Hold the requests of the block (and its tasks) to the per-call bound."""
    token = _call_slots.set(asyncio.Semaphore(_CALL_MAX_IN_FLIGHT))
    try:
        yield
    finally:
        _call_slots.reset(token)


async def report(message: str) -> None:
    """Tell the caller a stage of the call finished, when it listens."""
    if (hear := _reporter.get()) is not None:
        await hear(message)


async def together[A, B](
    first: Coroutine[Any, Any, A], second: Coroutine[Any, Any, B]
) -> tuple[A, B]:
    """Run two of a job's fetches at once; when one fails, cancel the other.

    Unlike ``gather``, no fetch outlives the job's session when its sibling
    raised: the error is the first one, unwrapped from the task group's.
    """
    try:
        async with asyncio.TaskGroup() as tg:
            a, b = tg.create_task(first), tg.create_task(second)
    except ExceptionGroup as group:
        raise group.exceptions[0] from None
    return a.result(), b.result()


@asynccontextmanager
async def job_session() -> AsyncIterator[None]:
    """Bind one keep-alive session to a place or search job, for its requests."""
    if not _KEEP_ALIVE:
        yield
        return
    async with sessions.bound(
        _PLUGIN, max_uses=_MAX_USES, max_streams=_MAX_STREAMS, keep_idle=_KEEP_IDLE
    ):
        yield


# XSSI guard Google prepends to its RPC JSON responses.
_XSSI_PREFIX = ")]}'"

# Consent cookie to dodge the EU consent interstitial that otherwise returns a
# page with no APP_INITIALIZATION_STATE. Mirrors the YouTube fetcher's SOCS.
CONSENT_COOKIES = {
    "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiADGgYIgOa_pgY",  # pragma: allowlist secret
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


# placeId -> fid. The pair never changes, so entries never expire; the bound
# only caps memory (~100 B an entry). Filled from every darray the RPCs return,
# so the common search-then-reviews pattern skips the place_id page GET.
_FID_CACHE_SIZE = 10_000
_fid_by_place_id: OrderedDict[str, str] = OrderedDict()

_PLACE_ID_RE = re.compile(r"place_id:([\w-]+)")
_AT_LATLNG_RE = re.compile(r"/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


def remember_fid(place_id: Any, fid: Any) -> None:
    """Cache one placeId -> fid pair, evicting the least recently used."""
    if not (isinstance(place_id, str) and place_id and isinstance(fid, str) and fid):
        return
    _fid_by_place_id[place_id] = fid
    _fid_by_place_id.move_to_end(place_id)
    while len(_fid_by_place_id) > _FID_CACHE_SIZE:
        _fid_by_place_id.popitem(last=False)


def remember_place(darray: Any) -> None:
    """Cache the placeId -> fid pair a place darray carries ([78] and [10])."""
    remember_fid(dig(darray, 78), dig(darray, 10))


def cached_fid(place_id: str) -> str | None:
    fid = _fid_by_place_id.get(place_id)
    if fid:
        _fid_by_place_id.move_to_end(place_id)
    return fid


def _is_name_only(resolved: ResolvedUrl) -> bool:
    """A ``/maps/place/<name>/`` URL with neither a fid nor a place_id in it."""
    return (
        resolved.kind == "place"
        and not resolved.fid
        and bool(resolved.value)
        and resolved.value != resolved.url
        and "place_id:" not in resolved.url
    )


async def resolve_fid(resolved: ResolvedUrl, *, language: str = "en") -> str | None:
    """Get a place's feature ID (see :func:`resolve_place`)."""
    fid, _ = await resolve_place(resolved, language=language)
    return fid


async def resolve_place(
    resolved: ResolvedUrl, *, language: str = "en"
) -> tuple[str | None, list | None]:
    """Get a place's feature ID: from the URL, the cache, a search or its HTML.

    Returns ``(fid, darray)``; ``darray`` is the place's search-result darray
    when a name lookup found it (its header fields equal the place RPC's), else
    ``None``. A ``/maps/place/...`` URL usually embeds the fid in its ``data=``
    blob. A ``?q=place_id:...`` URL or a shortlink does not, so we fetch the
    page once (unless the placeId is cached) and pull the fid out of the
    returned HTML. Raises :class:`SignInRequiredError` if Google serves a
    consent/sign-in wall instead of the page.
    """
    if resolved.fid:
        return resolved.fid, None
    match = _PLACE_ID_RE.search(resolved.url)
    place_id = match.group(1) if match else None
    if place_id and (fid := cached_fid(place_id)):
        return fid, None
    # Short links (maps.app.goo.gl / goo.gl) are Firebase Dynamic Links: a plain
    # GET only returns a JS interstitial, so render it — the JS follows the
    # redirect to the real /maps/place/… URL, from which we read the fid.
    # ponytail: browser render is slow (~30s) but it's the only way these
    # links resolve; they're rare and cached downstream by fid.
    if resolved.kind == "shortlink":
        rendered = await _fetch_html_stealthy(resolved.url, dict(CONSENT_COOKIES))
        return (extract_fid(rendered) if rendered else None), None
    # Name-only place URLs (e.g. /maps/place/Eiffel+Tower/) serve a JS-only
    # shell whose static HTML never contains the fid (even a headless render
    # won't navigate to the place), so that GET is skipped: one structured
    # search RPC gives the top result's fid and darray. The lite ``tbm=map``
    # page, which embeds fids in plain HTML, stays as the fallback.
    if _is_name_only(resolved):
        at = _AT_LATLNG_RE.search(resolved.url)
        fid, darray = await place_from_search(
            resolved.value,
            lat=float(at.group(1)) if at else None,
            lng=float(at.group(2)) if at else None,
            language=language,
        )
        if fid:
            return fid, darray
        return await fid_from_search(resolved.value, language=language), None
    html = await fetch_html(resolved.url)
    if html is not None:
        if looks_like_signin_wall(html):
            raise SignInRequiredError(
                f"Google returned a sign-in/consent wall for {resolved.url}"
            )
        fid = extract_fid(html)
        if fid:
            return fid, None
    if resolved.kind == "place" and resolved.value and resolved.value != resolved.url:
        return await fid_from_search(resolved.value, language=language), None
    return None, None


async def place_from_search(
    name: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    language: str = "en",
) -> tuple[str | None, list | None]:
    """Resolve a place name to ``(fid, darray)`` with one map-search RPC.

    Takes the top-ranked result, as the lite lookup did; ``lat``/``lng`` (a
    URL's ``@lat,lng``) centre the search there, to pick the right branch.
    """
    jd = await fetch_rpc_json(
        build_search_url(name, language=language, lat=lat, lng=lng), stage="search"
    )
    darrays = _search_darrays(jd)
    fid = dig(darrays[0], 10) if darrays else None
    if not isinstance(fid, str):
        return None, None
    remember_place(darrays[0])
    return fid, darrays[0]


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


def _wall_url(url: str) -> bool:
    """Is this Google's consent page or sorry page? Host and path, not the query."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host == "consent.google.com":
        return True
    google = host == "google.com" or host.endswith(".google.com")
    return google and parts.path.startswith("/sorry")


def _refused(response: http.RawResponse) -> bool:
    """Did Google refuse this exit: a 403/429, a sorry page or a sign-in wall?"""
    if response.status in http.BLOCK_STATUSES:
        return True
    location = response.location()
    if _wall_url(response.url) or (
        location and _wall_url(urljoin(response.url, location))
    ):
        return True
    # An RPC answer is JSON, never a wall, and its review text may quote one.
    if response.body[:16].lstrip().startswith(_XSSI_PREFIX.encode()):
        return False
    return looks_like_signin_wall(response.body[:5000].decode("utf-8", "replace"))


async def _send(
    url: str, *, stage: str, cookies: dict[str, str], attempt: int
) -> http.RawResponse:
    """One GET on the job's session, or on a fresh exit outside a job (or in a hedge)."""
    h = sessions.current()
    kw: dict[str, Any] = {
        "stage": stage,
        "headers": _HEADERS,
        "cookies": cookies,
        "timeout": _TIMEOUT,
        "attempt": attempt,
        "is_blocked": _refused,
    }
    if h is None:
        return await http.request(
            "GET", url, plugin=_PLUGIN, proxy=sessions.Exit().proxy_url(), **kw
        )
    return await h.request("GET", url, **kw)


async def _hedged_send(
    url: str, *, stage: str, cookies: dict[str, str], attempt: int
) -> http.RawResponse:
    after_s = _REVIEWS_HEDGE_AFTER_S if stage == "reviews" else _HEDGE_AFTER_S
    if _HEDGE_AFTER_S <= 0 or after_s <= 0:
        return await _send(url, stage=stage, cookies=cookies, attempt=attempt)
    # A hedge runs with no session bound, so it goes out on a fresh exit.
    return await hedged(
        lambda _: _send(url, stage=stage, cookies=cookies, attempt=attempt),
        after_s=after_s,
        accept=lambda r: not r.blocked,
        plugin=_PLUGIN,
        stage=stage,
    )


async def _get(
    url: str, *, stage: str, cookies: dict[str, str] | None = None
) -> http.RawResponse | None:
    """GET a Maps URL: rotate the exit on a refusal or a dead exit, then raise.

    Returns the 200 response, or ``None`` for another status Google answered
    with (a 404 means no such page: no new exit changes that). A refusal on
    every exit raises :class:`SignInRequiredError` for a sign-in wall, else
    :class:`GoogleRefusedError`: a 429 no longer reads as "no data".
    """
    merged = {**CONSENT_COOKIES, **(cookies or {})}
    h = sessions.current()
    slots = _call_slots.get()
    refusal = "no answer"
    last: http.RawResponse | None = None
    for attempt in range(_ATTEMPTS):
        seen = h.rotations if h is not None else 0
        try:
            # The slot is taken before the hedge clock starts: a request that
            # waits for one is queued, not slow.
            async with slots if slots is not None else nullcontext():
                r = await _hedged_send(
                    url, stage=stage, cookies=merged, attempt=attempt
                )
        except http.TransportError as e:
            refusal = f"{e.kind}: {e.detail}"
            if h is not None:
                await h.rotate(e.kind, seen=seen)
            continue
        if not r.blocked:
            await report(f"{stage} fetched")
            if r.status == 200:
                return r
            logger.warning("Maps GET %s returned %s", url, r.status)
            return None
        last, refusal = r, f"status {r.status}"
        await report(f"{stage} refused; trying a new exit")
        if h is not None:
            await h.rotate(refusal, seen=seen)
    if last is not None and last.status == 200:
        raise SignInRequiredError(f"Google returned a sign-in/consent wall for {url}")
    raise GoogleRefusedError(
        f"Google refused or did not answer the {stage} request on {_ATTEMPTS} "
        f"exits ({refusal})"
    )


async def fetch_html(url: str, *, stage: str = "page") -> str | None:
    """GET a Google Maps page and return its HTML.

    No browser fallback on a refusal (GMP-9): a new exit is what clears a 403
    or 429, and a headless render cost 10-30 s and a Chromium process.
    """
    r = await _get(url, stage=stage)
    return r.text() if r is not None else None


async def _fetch_html_stealthy(url: str, cookies: dict[str, str]) -> str | None:
    """Render a page in a browser: only shortlinks need it, their redirect runs in JS."""
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
# checked). It returns the FULL payload:
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

# NID session cookie pool. Google once trimmed the rich detail fields (counts,
# distribution, popular times, galleries, tags, most about sections) from
# responses that carried no session cookie; a plain GET to /maps mints an NID
# that unlocked them — no login, no browser. A small pool is rotated
# round-robin (mirrors the YouTube fetcher's ``_RotatingSession``); each
# expires after a TTL and is re-minted lazily.
#
# Off by default: on 2026-10-14 the place RPC parsed identically with and
# without an NID (two places), and a cold slot's mint held the RPC back by
# 1.1-3.7 s. GOOGLE_MAPS_SKIP_NID_MINT=0 brings the mint back should Google
# re-gate the fields; delete the pool once prod shows no field loss.
_SKIP_NID_MINT = os.getenv("GOOGLE_MAPS_SKIP_NID_MINT", "1") != "0"
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
        r = await http.request(
            "GET",
            "https://www.google.com/maps?hl=en",
            plugin=_PLUGIN,
            stage="nid",
            proxy=sessions.Exit().proxy_url(),
            headers=_HEADERS,
            cookies=CONSENT_COOKIES,
            timeout=_TIMEOUT,
        )
        return r.cookies.get("NID")
    except http.TransportError as e:
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
    place-field paths index into), or ``None`` on failure. The full-page pb
    selector (``_PLACE_DETAIL_PB``) is what brings the full payload.
    """
    pb = _PLACE_DETAIL_PB.format(fid=fid)
    url = (
        "https://www.google.com/maps/preview/place"
        f"?authuser=0&hl={language}&gl=us&pb={quote(pb, safe='!')}"
    )
    cookies = None if _SKIP_NID_MINT else await get_session_cookies()
    jd = await fetch_rpc_json(url, stage="place", cookies=cookies)
    darray = jd[6] if isinstance(jd, list) and len(jd) > 6 else None
    if not isinstance(darray, list):
        return None
    remember_place(darray)
    _watch_field_loss(darray)
    return darray


# Detail answers that came back without the review fields the NID once unlocked.
# The GMP-3 prod watch greps for this warning before the NID pool is deleted.
_field_loss = 0


def _watch_field_loss(darray: list) -> None:
    """Warn, counted, when a place with reviews lacks its distribution or tags."""
    global _field_loss
    count = dig(darray, 4, 8)
    if not isinstance(count, int | float) or count <= 0:
        return
    missing = [] if isinstance(dig(darray, 175, 3), list) else ["distribution"]
    # Only a well-reviewed place is sure to have tags.
    if count >= 100 and not _reviews_tags(darray):
        missing.append("tags")
    if missing:
        _field_loss += 1
        logger.warning(
            "[google_maps] detail field loss #%d: %s has %d reviews but no %s",
            _field_loss,
            dig(darray, 10),
            int(count),
            " or ".join(missing),
        )


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
        async with aclosing(
            ordered_map(
                urls, lambda u: fetch_rpc_json(u, stage="search"), concurrency=wave
            )
        ) as pages:
            async for jd in pages:
                darrays = _search_darrays(jd)
                if not darrays:
                    return
                for darray in darrays:
                    remember_place(darray)
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
        node = _reviews_node(await fetch_rpc_json(url, stage="reviews"))
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
    url: str, *, stage: str = "rpc", cookies: dict[str, str] | None = None
) -> Any | None:
    """GET a Maps ``/maps/preview/*`` RPC URL and return parsed JSON.

    These endpoints return an XSSI-guarded JSON array (not HTML). Returns the
    decoded structure, or ``None`` for a non-200 answer or a non-JSON body.
    Raises as :func:`_get` does when Google refuses every exit.
    """
    r = await _get(url, stage=stage, cookies=cookies)
    if r is None:
        return None
    # Review pages reach ~1 MB: decode off the loop.
    return await asyncio.to_thread(_decode_rpc_body, r.body)


_decoder = json.JSONDecoder()


def _decode_rpc_body(body: bytes | str) -> Any | None:
    """Strip the XSSI guard and decode the top-level JSON blob after it.

    ``raw_decode`` reads the blob and ignores whatever trails it, at C speed
    (0.1-1.2 ms against 40-64 ms for the pure-Python brace scan, which stays as
    the fallback for a body it cannot read).
    """
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    text = strip_xssi(text)
    start = next((i for i, c in enumerate(text) if c in "[{"), -1)
    if start == -1:
        return None
    try:
        return _decoder.raw_decode(text, start)[0]
    except ValueError:
        blob = brace_match_json(text, start)
        try:
            return json.loads(blob) if blob else None
        except ValueError:
            return None
