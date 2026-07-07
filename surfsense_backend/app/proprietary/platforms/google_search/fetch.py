"""Proxy-aware fetch seam for the Google Search scraper.

Google's web ``/search`` endpoint is far more hostile than Maps: most
residential IPs get a 429 "unusual traffic" wall, and the ones that pass serve
a JavaScript shell whose organic results only materialize after the page's JS
runs. So a plain GET is never enough — we need a *non-blocked* IP **and** a real
browser render, both on the same IP.

Strategy (measured against DataImpulse residential IPs, ~50% pass rate):

1. **Reuse the last good IP.** A sticky IP that just served a real SERP is the
   best predictor of the next success, so it's cached module-wide and only a
   <1 s re-precheck stands between it and the render.
2. **Vet fresh IPs cheaply and in parallel.** A curl_cffi GET costs ~90 KB and
   tells us in <1 s whether an IP is walled; several candidates race at once
   and the first pass wins. Rotating gateways (``:823``) hand a fresh IP per
   request, which makes a *browser* session look like a botnet — so we pin a
   per-attempt **sticky** port (one IP for the whole precheck+render) via
   :func:`_sticky_variant`.
3. **Render on the vetted IP.** Only then do we spend the headless render,
   reusing the same sticky IP. The browser itself is launched **once** and kept
   alive module-wide (:func:`_get_session`); each fetch only opens a fresh
   context on the vetted proxy, cutting ~5 s of launch cost per page.
4. **Retry across IPs** until one yields real results or we exhaust the budget.

``ponytail:`` sticky-port rewriting is DataImpulse-specific (its gateway maps
ports→sessions); other providers just reuse their single URL. The upgrade path
if we add another sticky vendor is to extend ``_STICKY_HOSTS``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

try:  # browser tier is optional (needs `scrapling[fetchers]` browsers installed)
    from scrapling.fetchers import AsyncStealthySession, ProxyRotator
except Exception:  # pragma: no cover - import guard
    AsyncStealthySession = None  # type: ignore[assignment]
    ProxyRotator = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Consent cookies to dodge the EU interstitial (mirrors the Maps/YouTube seams).
CONSENT_COOKIES = {"CONSENT": "PENDING+987", "SOCS": "CAESHAgBEhIaAB"}
_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Gateways whose sticky sessions are selected by destination port. A random port
# in this range pins one residential IP for the duration of a browser session.
_STICKY_HOSTS = {"gw.dataimpulse.com"}
_STICKY_PORT_RANGE = (10000, 20000)

# How many distinct IPs to try before giving up on a page. Prechecks are cheap
# and now run in parallel, so the budget is generous — it only bites during a
# rate-limited window where most IPs are walled.
_MAX_IP_ATTEMPTS = 24
# How many fresh sticky IPs to precheck concurrently per vetting round. At
# ~50% pass rate, 4 in parallel almost always yields a winner in one ~1 s
# round instead of a serial walk.
_VET_CONCURRENCY = 4
# When a whole vetting round comes back walled, Google is rate-limiting this
# egress; a short pause before the next round lets it cool instead of burning
# the budget in a couple of seconds.
_WALLED_ROUND_BACKOFF_S = 3.0

# The sticky IP that most recently served a real SERP; the strongest hint for
# the next fetch. Re-vetted (cheap) before reuse, dropped on failure.
# ponytail: a single slot, not a pool — concurrent fetches share (and race)
# it; worst case a loser re-vets a fresh IP, which is the normal path anyway.
_last_good_proxy: str | None = None

# A usable precheck responds in <1 s; anything slower is a dead/slow sticky IP
# (seen hanging ~60 s). Abandon it on this deadline so a slow IP costs no more
# than a walled one, keeping per-page time predictable.
_PRECHECK_TIMEOUT_S = 5.0

# A walled response is small and says so; the anti-bot page never carries the
# results container. Precheck (small shell page) keys off the text markers;
# the rendered page is judged structurally (presence of the results container),
# because a *good* rendered SERP embeds "/sorry/" etc. inside its own scripts.
_BLOCK_MARKERS = ("unusual traffic", "detected unusual", "/sorry/")
# Desktop markers + the mobile lightweight layout's result-block class.
_RESULTS_MARKERS = ('id="rso"', 'id="search"', 'class="tF2Cxc', "Gx5Zad")


def _sticky_variant(proxy_url: str | None) -> str | None:
    """Pin a random sticky port for gateways that key sessions by port.

    For a rotating gateway this converts ``…@gw.dataimpulse.com:823`` (new IP
    per request) into ``…@gw.dataimpulse.com:<10000-20000>`` (one IP held for
    the whole browser session). Non-sticky providers are returned unchanged.
    """
    if not proxy_url:
        return None
    parts = urlsplit(proxy_url)
    if parts.hostname not in _STICKY_HOSTS:
        return proxy_url
    port = random.randint(*_STICKY_PORT_RANGE)
    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        userinfo += "@"
    netloc = f"{userinfo}{parts.hostname}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _is_walled(html: str | None) -> bool:
    """True for the small anti-bot interstitial (precheck GET use)."""
    low = (html or "").lower()
    return any(m in low for m in _BLOCK_MARKERS)


def _has_results(html: str | None) -> bool:
    """True when the rendered DOM carries the organic results container.

    A fully-rendered SERP is ~1 MB and legitimately mentions ``/sorry/`` etc.
    inside its own scripts, so the render is judged by *structure* (the results
    container is present) rather than by text markers.
    """
    return any(m in (html or "") for m in _RESULTS_MARKERS)


async def _precheck(url: str, proxy: str | None) -> bool:
    """Cheap GET to decide if this IP is walled (True = looks usable)."""
    try:
        r = await AsyncFetcher.get(
            url,
            cookies=CONSENT_COOKIES,
            proxy=proxy,
            stealthy_headers=True,
            timeout=_PRECHECK_TIMEOUT_S,
        )
    except Exception as e:
        # A timeout (slow/dead IP) lands here too; treat it like a walled IP.
        logger.debug("[google_search] precheck error: %s", e)
        return False
    return r.status == 200 and not _is_walled(r.html_content)


async def _vet_fresh_ip(url: str, base: str) -> str | None:
    """Race prechecks on :data:`_VET_CONCURRENCY` fresh sticky IPs.

    The first IP to pass wins and the rest are cancelled, so one round costs
    about one precheck (~1 s) instead of a serial walk over walled IPs.
    """

    async def vet(proxy: str | None) -> str | None:
        return proxy if await _precheck(url, proxy) else None

    tasks = [
        asyncio.create_task(vet(_sticky_variant(base))) for _ in range(_VET_CONCURRENCY)
    ]
    winner: str | None = None
    for fut in asyncio.as_completed(tasks):
        winner = await fut
        if winner:
            break
    for task in tasks:
        task.cancel()
    return winner


# People-also-ask answers only load when a question is expanded (clicked).
# We expand just the initially-served questions (~4); each expansion appends
# more questions we deliberately leave collapsed, or the loop never ends.
# All clicks are fired first and the XHRs load concurrently behind one shared
# wait, instead of a serial click→wait per question.
_PAA_EXPAND_LIMIT = 4
_PAA_ANSWER_WAIT_MS = 1500
# The AI Overview's "Show more" clamp, when present.
_AIO_SHOW_MORE_SEL = "[aria-label='Show more AI Overview']"


async def _expand_blocks(page):
    """Click open the lazy SERP blocks so their content renders into the DOM.

    Runs inside the browser render (Playwright async API — the persistent
    session's ``page_action`` must be a coroutine). Two expansions:

    * AI Overview "Show more" (``ponytail:`` clicked unconditionally, so the
      full overview is always scraped and ``scrapeFullAiOverview`` needs no
      plumbing down here — a superset of the actor's gated behavior).
    * The initially-served People-Also-Ask questions (answers load on click).

    Both are free on pages without the block, and best-effort: a failed click
    just leaves that section collapsed rather than failing the render.
    """
    clicked = 0
    try:
        more = await page.query_selector(_AIO_SHOW_MORE_SEL)
        if more:
            await more.click(timeout=1500)
            clicked += 1
    except Exception:  # clamp absent/detached; the collapsed text still parses
        pass
    try:
        pairs = await page.query_selector_all("div.related-question-pair")
        for pair in pairs[:_PAA_EXPAND_LIMIT]:
            try:
                await pair.click(timeout=1500)
                clicked += 1
            except Exception:  # stale handle/overlay; skip pair
                continue
    except Exception as e:  # never fail the render over PAA
        logger.debug("[google_search] PAA expansion skipped: %s", e)
    if clicked:
        # One shared wait while all the answer XHRs land in parallel.
        await page.wait_for_timeout(_PAA_ANSWER_WAIT_MS)
    return page


# Firefox-on-Android UA to make Google serve its mobile lightweight layout.
# ponytail: the engine underneath is patchright's *Chromium*, so this UA lies
# about the engine — but empirically it's what gets the mobile layout served
# without tripping Google's wall. A Chrome-on-Android UA (the "coherent"
# choice) gets 429-walled on every IP, so don't switch it back without a live
# mobile e2e proving the layout still loads.
_MOBILE_UA = "Mozilla/5.0 (Android 14; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0"
_MOBILE_VIEWPORT = {"width": 412, "height": 915}


# patchright launches Chromium via asyncio.create_subprocess_exec, which the
# server's main loop cannot do on Windows (main.py pins a SelectorEventLoop
# for psycopg; Selector loops raise NotImplementedError on subprocess_exec).
# All browser work therefore runs on ONE dedicated background loop that is
# explicitly subprocess-capable; callers await it across threads. This also
# keeps the persistent AsyncStealthySession (and its async page_action) intact
# — the sync-fetcher-in-a-thread pattern the other scrapers use would tear
# down the browser on every fetch.
_browser_loop: asyncio.AbstractEventLoop | None = None
_browser_loop_guard = threading.Lock()


def _get_browser_loop() -> asyncio.AbstractEventLoop:
    """The lazily-started, process-wide event loop the browser lives on."""
    global _browser_loop
    with _browser_loop_guard:
        if _browser_loop is None:
            loop = (
                asyncio.ProactorEventLoop()
                if sys.platform == "win32"
                else asyncio.new_event_loop()
            )
            threading.Thread(
                target=loop.run_forever, name="google-search-browser", daemon=True
            ).start()
            _browser_loop = loop
        return _browser_loop


async def _in_browser_loop(coro):
    """Run ``coro`` on the browser loop and await its result from this loop."""
    return await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(coro, _get_browser_loop())
    )


# One live browser per layout (desktop / mobile — the UA and viewport are
# session-level context options). Launching Chromium costs ~5 s, so it's paid
# once and every fetch just opens a fresh context on its vetted sticky proxy.
# Only ever touched from coroutines running on the browser loop.
_sessions: dict[bool, AsyncStealthySession] = {}
_session_lock = asyncio.Lock()

# How many renders may run at once. scrapling's page pool defaults to ONE
# page, and a per-fetch proxy context skips its wait-for-a-slot path, so a
# second concurrent render raised RuntimeError('Maximum page limit (1)
# reached'); the failure handler then closed the shared browser under the
# sibling render (the TargetClosedError cascade seen in production when
# several scrape runs overlap). The pool and this gate are sized together:
# the gate queues excess renders instead of tripping the pool.
_MAX_CONCURRENT_PAGES = 4
# Only ever awaited from coroutines running on the browser loop.
_render_gate = asyncio.Semaphore(_MAX_CONCURRENT_PAGES)

# Live renders per session, so dropping a "broken" session defers the actual
# browser close until its last in-flight render finishes — closing earlier is
# what murdered sibling renders. Browser-loop-only state.
_inflight: dict[AsyncStealthySession, int] = {}
_doomed: set[AsyncStealthySession] = set()


async def _get_session(mobile: bool) -> AsyncStealthySession:
    """The shared live browser session for this layout, launching it if needed."""
    async with _session_lock:
        session = _sessions.get(mobile)
        if session is not None:
            return session
        kwargs: dict = {
            "headless": True,
            "network_idle": True,
            "google_search": True,
            "page_action": _expand_blocks,
            "retries": 1,  # our own IP loop is the retry policy
            "max_pages": _MAX_CONCURRENT_PAGES,
        }
        base = get_proxy_url()
        if base:
            # Rotator mode makes the session launch a plain browser so each
            # fetch can carry its own vetted sticky proxy; the rotator itself
            # is never consulted because every fetch passes an explicit proxy.
            kwargs["proxy_rotator"] = ProxyRotator([base])
        if mobile:
            kwargs["useragent"] = _MOBILE_UA
            kwargs["additional_args"] = {"viewport": _MOBILE_VIEWPORT}
        session = AsyncStealthySession(**kwargs)
        await session.start()
        _sessions[mobile] = session
        return session


async def _drop_session_on_loop(mobile: bool) -> None:
    async with _session_lock:
        session = _sessions.pop(mobile, None)
    if session is None:
        return
    if _inflight.get(session, 0):
        # Sibling renders are still on this browser; the last one closes it.
        _doomed.add(session)
        return
    with contextlib.suppress(Exception):  # already dead; nothing to salvage
        await session.close()


async def _drop_session(mobile: bool) -> None:
    """Close and forget a session whose browser is presumed broken."""
    await _in_browser_loop(_drop_session_on_loop(mobile))


async def close_sessions() -> None:
    """Shut down the shared browsers (for tests/scripts wanting a clean exit)."""
    for mobile in (False, True):
        await _drop_session(mobile)


async def _render_on_loop(url: str, proxy: str | None, mobile: bool):
    async with _render_gate:
        session = await _get_session(mobile)
        _inflight[session] = _inflight.get(session, 0) + 1
        try:
            return await session.fetch(url, proxy=proxy)
        finally:
            _inflight[session] -= 1
            if not _inflight[session]:
                del _inflight[session]
                if session in _doomed:
                    _doomed.discard(session)
                    with contextlib.suppress(Exception):
                        await session.close()


async def _render(url: str, proxy: str | None, mobile: bool = False):
    """Headless render of a SERP on the shared browser (fresh proxy context).

    The actual browser work is marshalled onto the dedicated subprocess-capable
    loop (see :func:`_get_browser_loop`); this coroutine just awaits it from
    the caller's loop.
    """
    return await _in_browser_loop(_render_on_loop(url, proxy, mobile))


async def fetch_serp_html(url: str, *, mobile: bool = False) -> str | None:
    """Return fully-rendered SERP HTML for ``url``, or ``None`` if unobtainable.

    Reuses the last known-good sticky IP when it still passes the cheap
    precheck; otherwise races prechecks on fresh sticky IPs and renders on the
    first that passes. Retries until a render returns real results or the IP
    budget runs out. Requires the browser tier — without it we cannot get
    JS-built results. ``mobile`` renders with a phone UA/viewport (the
    ``mobileResults`` input).
    """
    global _last_good_proxy
    if AsyncStealthySession is None:
        logger.error("[google_search] browser tier unavailable; cannot render SERPs")
        return None

    base = get_proxy_url()
    ips_tried = 0
    while ips_tried < _MAX_IP_ATTEMPTS:
        if base:
            if _last_good_proxy and await _precheck(url, _last_good_proxy):
                proxy = _last_good_proxy
            else:
                _last_good_proxy = None
                proxy = await _vet_fresh_ip(url, base)
                ips_tried += _VET_CONCURRENCY
                if proxy is None:
                    logger.debug("[google_search] vetting round: all IPs walled")
                    await asyncio.sleep(_WALLED_ROUND_BACKOFF_S)
                    continue
        else:
            proxy = None
            ips_tried += 1
        started = time.perf_counter()
        try:
            page = await _render(url, proxy, mobile=mobile)
        except Exception as e:
            # Renders on a walled IP still return HTML; an exception means the
            # browser side is broken, so relaunch it rather than limp along.
            # repr(), not str(): e.g. NotImplementedError stringifies to "".
            logger.warning("[google_search] render failed: %r", e)
            _last_good_proxy = None
            await _drop_session(mobile)
            continue
        fetch_ms = (time.perf_counter() - started) * 1000
        html = page.html_content or ""
        good = page.status == 200 and _has_results(html)
        logger.info(
            "[google_search][perf] status=%s bytes=%d has_results=%s fetch_ms=%.0f reused_ip=%s",
            page.status,
            len(html),
            good,
            fetch_ms,
            proxy == _last_good_proxy,
        )
        if good:
            _last_good_proxy = proxy
            return html
        _last_good_proxy = None
    logger.warning("[google_search] exhausted %d IPs for %s", _MAX_IP_ATTEMPTS, url)
    return None
