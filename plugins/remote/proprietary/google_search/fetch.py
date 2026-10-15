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
   per-attempt **sticky** session (one IP for the whole precheck+render) via
   :func:`_sticky_proxy`.
3. **Render on the vetted IP.** Only then do we spend the headless render,
   reusing the same sticky IP. The browser itself is launched **once** and kept
   alive module-wide (:func:`_get_session`); each fetch only opens a fresh
   context on the vetted proxy, cutting ~5 s of launch cost per page.
4. **Retry across IPs** until one yields real results or we exhaust the budget.

Each attempt pins one sticky IP through the proxy provider's own session
syntax (DataImpulse's sticky ports, NodeMaven's ``-sid-``), so any vendor that can
hold a session gets the pool.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable, Iterable
from contextvars import ContextVar
from typing import Protocol
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from proprietary.google_search import captcha as _captcha
from proprietary.google_search import pool_store as _store
from proprietary.scraping import http, lifecycle
from proprietary.scraping.browser_loop import in_browser_loop as _in_browser_loop
from proprietary.scraping.captcha import captcha_enabled, get_captcha_config
from proprietary.scraping.proxy import get_proxy_url, get_sticky_proxy_url

try:  # browser tier is optional (needs `scrapling[fetchers]` browsers installed)
    from scrapling.fetchers import AsyncStealthySession, ProxyRotator
except Exception:  # pragma: no cover - import guard
    AsyncStealthySession = None  # type: ignore[assignment]
    ProxyRotator = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Consent cookies to dodge the EU interstitial (mirrors the Maps/YouTube seams).
CONSENT_COOKIES = {"CONSENT": "PENDING+987", "SOCS": "CAESHAgBEhIaAB"}
_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Context-cookie form of the consent cookies, injected before a render's
# navigation (page_setup) when captcha solving is on, so the browser skips the
# EU interstitial exactly like the curl precheck does.
_CONSENT_CTX = [
    {"name": k, "value": v, "domain": ".google.com", "path": "/"}
    for k, v in CONSENT_COOKIES.items()
]

# GOOGLE_ABUSE_EXEMPTION cookies harvested per sticky proxy after a solve. A hit
# lets a later render on the same IP skip straight to results (no re-solve),
# amortizing the one paid solve across the sticky session.
# ponytail: keyed by the full proxy URL (incl. sticky port). When that port's
# exit IP rotates the cached cookie goes stale -> the next render re-hits
# /sorry, re-solves, and overwrites the entry. Self-correcting; the sticky-port
# space is small so the dict never grows unbounded in practice.
_exemption_jar: dict[str, list[dict]] = {}

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

# Warm sticky-IP pool. Concurrent fetches spread renders across the pool's IPs
# instead of funneling every render onto one sticky IP (a single hot residential
# IP is exactly what Google re-walls), and each pool IP is solved **once** — so
# steady-state paid solves track the pool size, not the request count. Replaces
# the old single "_last_good_proxy" slot, which both funneled load and forced a
# fresh solve whenever it was raced to None.
#
# State is touched from two loops (fetch_serp_html on the request loop; the
# exemption write in page_action on the browser loop), so a small lock guards
# every mutation. No awaits are held under the lock — every critical section is
# a handful of dict ops.
_pool: dict[str, float] = {}  # warm proxy url -> last-used monotonic ts
_pool_inflight: dict[str, int] = {}  # proxy url -> renders currently pinned to it
_pool_pending = 0  # fresh vets/solves in flight (growing the pool toward target)
_pool_lock = threading.Lock()

# Target number of warm IPs to keep. Sized for throughput: it must cover
# (target SERP/min) / (safe SERP/min per IP), so a fleet serving 500/min across
# a handful of processes wants this in the low tens. Env-tunable without a code
# change; per-IP concurrency is a soft cap (exceeded only when the pool is full
# and every IP is busy, because reusing a warm IP always beats a fresh solve).
_WARM_POOL_TARGET = int(os.getenv("GOOGLE_SEARCH_WARM_POOL_TARGET", "8"))
_WARM_IP_MAX_CONCURRENCY = int(os.getenv("GOOGLE_SEARCH_IP_MAX_CONCURRENCY", "2"))
# When the pool is full and every IP is at its cap, wait this long for a slot to
# free instead of vetting+solving a fresh IP (this backpressure is what bounds
# solves to ~pool size under a burst).
_POOL_WAIT_S = 0.25
# Absolute per-fetch budget. A cold solve is ~45 s and we may retry a couple of
# walled IPs, but a fetch that can't get results within this window fails rather
# than hanging a request forever under saturation.
_FETCH_DEADLINE_S = float(os.getenv("GOOGLE_SEARCH_FETCH_DEADLINE_S", "180"))

# A usable precheck responds in <1 s; anything slower is a dead/slow sticky IP
# (seen hanging ~60 s). Abandon it on this deadline so a slow IP costs no more
# than a walled one, keeping per-page time predictable. (connect incl. the
# proxy CONNECT and TLS, read), one attempt: Scrapling's own retries had a dead
# IP cost about 17 s.
_PRECHECK_TIMEOUT_S = 5.0
_PRECHECK_TIMEOUT = (_PRECHECK_TIMEOUT_S, _PRECHECK_TIMEOUT_S)

# A walled response is small and says so; the anti-bot page never carries the
# results container. Precheck (small shell page) keys off the text markers;
# the rendered page is judged structurally (presence of the results container),
# because a *good* rendered SERP embeds "/sorry/" etc. inside its own scripts.
_BLOCK_MARKERS = ("unusual traffic", "detected unusual", "/sorry/")
# Desktop markers + the mobile lightweight layout's result-block class.
_RESULTS_MARKERS = ('id="rso"', 'id="search"', 'class="tF2Cxc', "Gx5Zad")


class LinkSink(Protocol):
    """Takes a render's ``/goto`` hrefs as soon as they attach (GS-3)."""

    def feed(self, hrefs: Iterable[str]) -> None: ...  # thread-safe
    def discard(self) -> None: ...  # request loop: that render was not returned


# Set by the scraper around a page's fetch: the render feeds its /goto links
# here so they resolve while the page is still expanding. None skips the read.
link_sink: ContextVar[LinkSink | None] = ContextVar("google_search_links", default=None)
# Set by the caller for MCP progress at each attempt (request loop only).
stage_hook: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "google_search_stage", default=None
)


async def _stage(message: str) -> None:
    hook = stage_hook.get()
    if hook is not None:
        with contextlib.suppress(Exception):  # progress never fails a render
            await hook(message)


def _sticky_proxy() -> str | None:
    """A fresh sticky session: one residential IP for a whole precheck and render.

    No country is pinned: DataImpulse's per-country pools are walled even for the
    precheck, and the URL's ``gl=`` sets the results' locale instead.
    """
    return get_sticky_proxy_url(f"gs{uuid4().hex[:12]}")


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


def _precheck_blocked(response: http.RawResponse) -> bool:
    return response.status != 200 or _is_walled(response.text())


async def _precheck(url: str, proxy: str | None) -> bool:
    """Cheap GET to decide if this IP is walled (True = looks usable)."""
    try:
        r = await http.request(
            "GET",
            url,
            plugin="google-search",
            stage="precheck",
            proxy=proxy,
            cookies=CONSENT_COOKIES,
            timeout=_PRECHECK_TIMEOUT,
            is_blocked=_precheck_blocked,
        )
    except Exception as e:
        # A timeout (slow/dead IP) lands here too; treat it like a walled IP.
        logger.debug("[google_search] precheck error: %s", e)
        return False
    return not r.blocked


async def _vet_fresh_ip(url: str) -> str | None:
    """Race prechecks on :data:`_VET_CONCURRENCY` fresh sticky IPs.

    The first IP to pass wins and the rest are cancelled, so one round costs
    about one precheck (~1 s) instead of a serial walk over walled IPs.
    """

    async def vet(proxy: str | None) -> str | None:
        return proxy if await _precheck(url, proxy) else None

    tasks = [asyncio.create_task(vet(_sticky_proxy())) for _ in range(_VET_CONCURRENCY)]
    winner: str | None = None
    for fut in asyncio.as_completed(tasks):
        winner = await fut
        if winner:
            break
    for task in tasks:
        task.cancel()
    return winner


def _pool_take() -> tuple[str, str | None]:
    """Decide how the next render gets an IP. Returns one of:

    * ``("reuse", url)`` — an existing warm IP under its soft concurrency cap
      (its inflight count is already incremented; caller must ``_pool_settle``),
    * ``("grow", None)`` — pool is below target, caller should vet a fresh IP
      and solve on it (a pending slot is reserved),
    * ``("wait", None)`` — pool is full and every IP is busy; caller should wait
      briefly and retry rather than burn a fresh solve.

    Reuse prefers the least-loaded, least-recently-used warm IP so concurrent
    renders fan out across the pool instead of piling onto one IP.
    """
    global _pool_pending
    with _pool_lock:
        best: tuple[str, int, float] | None = None
        for url, last in _pool.items():
            n = _pool_inflight.get(url, 0)
            if n < _WARM_IP_MAX_CONCURRENCY and (
                best is None or (n, last) < (best[1], best[2])
            ):
                best = (url, n, last)
        if best is not None:
            _pool_inflight[best[0]] = _pool_inflight.get(best[0], 0) + 1
            return ("reuse", best[0])
        if len(_pool) + _pool_pending < _WARM_POOL_TARGET:
            _pool_pending += 1
            return ("grow", None)
        return ("wait", None)


def _pool_bind_fresh(url: str) -> None:
    """Pin the first render onto a just-vetted fresh IP (grow path)."""
    with _pool_lock:
        _pool_inflight[url] = _pool_inflight.get(url, 0) + 1


def _pool_adopt(url: str) -> None:
    """Turn a reserved grow slot into an IP adopted from the shared store: it
    joins the warm pool without a local solve, so release the pending reservation
    and pin this render onto it."""
    global _pool_pending
    with _pool_lock:
        _pool_pending = max(0, _pool_pending - 1)
        _pool[url] = time.monotonic()
        _pool_inflight[url] = _pool_inflight.get(url, 0) + 1


def _pool_abort_grow() -> None:
    """Release a reserved grow slot when the fresh vet found no usable IP."""
    global _pool_pending
    with _pool_lock:
        _pool_pending = max(0, _pool_pending - 1)


def _pool_settle(url: str, *, good: bool | None, grew: bool) -> None:
    """Finish a render: drop its inflight hold, then admit or evict the IP.

    A good render (re)admits the IP to the warm pool (refreshing its LRU stamp);
    a walled render evicts it and drops its now-worthless cached exemption.
    ``good`` None is a cancelled render, which says nothing about the IP: a
    warm one keeps its standing (a sibling may have evicted it meanwhile), and
    a fresh one joins only when its paid solve already landed.
    """
    global _pool_pending
    with _pool_lock:
        n = _pool_inflight.get(url, 0) - 1
        if n <= 0:
            _pool_inflight.pop(url, None)
        else:
            _pool_inflight[url] = n
        if grew:
            _pool_pending = max(0, _pool_pending - 1)
        if good is None:
            if grew and _exemption_jar.get(url):
                _pool[url] = time.monotonic()
        elif good:
            _pool[url] = time.monotonic()
        else:
            _pool.pop(url, None)
            _exemption_jar.pop(url, None)


# People-also-ask answers only load when a question is expanded (clicked).
# We expand just the initially-served questions (~4); each expansion appends
# more questions we deliberately leave collapsed, or the loop never ends.
# All clicks are fired first and the XHRs load concurrently behind one shared
# wait, instead of a serial click→wait per question.
_PAA_EXPAND_LIMIT = 4
_PAA_ANSWER_WAIT_MS = 1500
# The AI Overview's "Show more" clamp, when present.
_AIO_SHOW_MORE_SEL = "[aria-label='Show more AI Overview']"

# Event-driven settle (on by default; GOOGLE_SEARCH_FAST_SETTLE=0 restores the
# network-idle wait and the fixed-sleep expansion). Google's telemetry pings
# keep the network busy, so network idle cost 5.1-5.8 s on every render for
# nothing the parser reads; the expansion now waits on the answers themselves.
_FAST_SETTLE = os.getenv("GOOGLE_SEARCH_FAST_SETTLE", "1") != "0"
# Organic results of the desktop and the mobile layout. Never ``#rso``: the JS
# shell that reloads itself with ``sei`` carries it too.
_READY_SEL = "div.tF2Cxc, div.Gx5Zad"
_LOAD_TIMEOUT_MS = 8000
_READY_TIMEOUT_MS = 2000
# The PAA question's own toggle; clicking the pair div waited on actionability.
_PAA_TOGGLE_SEL = "div.related-question-pair [role=button][aria-expanded='false']"
_CLICK_TIMEOUT_MS = 500
_PAA_ANSWER_CAP_MS = 2500
_PAA_RETRY_CAP_MS = 1000
# Some pages insert the PAA block after the load event; network idle used to
# cover that. Page 1 of a plain desktop query waits this long for it to attach
# (the mobile layout pre-renders its PAA in other markup).
_PAA_SEL = "div.related-question-pair"
_PAA_ATTACH_MS = 1500
# Each expansion makes Google append a couple of questions, their answers
# preloaded (the old fixed wait returned 9-12 answered questions for 4 clicks).
# Once the clicked ones are answered, wait until the block stops changing for
# _PAA_STABLE_MS, capped at _PAA_GRACE_CAP_MS. The appended answers trickle in
# over seconds: on 'rust programming language' 400/1500 and 600/2000 got the 4
# clicked answers (4-9 questions, expansion 1.6-3.4 s), 800/3000 got 12 of
# 12-15 (expansion 7.1-7.4 s, a warm render slower than the old path's), where
# the old path got 6-12. Raise these for the answers at that price.
_PAA_STABLE_MS = int(os.getenv("GOOGLE_SEARCH_PAA_STABLE_MS", "400"))
_PAA_GRACE_CAP_MS = int(os.getenv("GOOGLE_SEARCH_PAA_GRACE_MS", "1500"))
# The AI Overview streams in and may attach after the PAA clicks. It is read
# once its text held its length for _AIO_STABLE_MS, capped: waiting only for
# its first paragraph read 0-680 of its ~2.5k characters.
_AIO_STABLE_MS = int(os.getenv("GOOGLE_SEARCH_AIO_STABLE_MS", "500"))
_AIO_PROSE_CAP_MS = 2000
# True once each of the first ``n`` pairs holds an answer (snippet or AI).
_PAA_ANSWERED_JS = """(n) => {
  const pairs = [...document.querySelectorAll('div.related-question-pair')].slice(0, n);
  return pairs.every(p => p.querySelector('.hgKElc, .n6owBd, .LGOjhe, #m-x-content'));
}"""
# True once the question and answer counts held still for ``ms``.
_PAA_STABLE_JS = """(ms) => {
  const pairs = [...document.querySelectorAll('div.related-question-pair')];
  const answered = pairs.filter(
    p => p.querySelector('.hgKElc, .n6owBd, .LGOjhe, #m-x-content')).length;
  const key = pairs.length + ':' + answered;
  const now = performance.now();
  const seen = window.__gsPaaSeen;
  if (!seen || seen.key !== key) {
    window.__gsPaaSeen = {key, since: now};
    return false;
  }
  return now - seen.since >= ms;
}"""
# The /goto links the parser will carry, picked as it picks them: each organic
# block's first result anchor and sitelink once the results attach; then each PAA
# answer's titled source and each AI Overview source. Only those: a SERP holds
# 64-109 distinct /goto links, against 9-19 that the parser keeps.
_LINKS_JS = """(expanded) => {
  const target = h => h && /^(http|\\/url\\?|\\/goto\\?)/.test(h);
  const first = root => [...root.querySelectorAll('a')]
    .find(a => target(a.getAttribute('href')));
  const goto = a => {
    const h = a && a.getAttribute('href');
    return h && h.startsWith('/goto?') ? h : null;
  };
  const out = [...document.querySelectorAll('div.tF2Cxc')].map(b => goto(first(b)));
  for (const cell of document.querySelectorAll('td.cIkxbf')) {  // sitelinks
    if (cell.querySelector('h3')) out.push(goto(first(cell)));
  }
  if (expanded) {
    for (const pair of document.querySelectorAll('div.related-question-pair')) {
      out.push(goto([...pair.querySelectorAll('a')]
        .find(a => a.querySelector('h3') && target(a.getAttribute('href')))));
    }
    let sources = document.querySelectorAll('li.Ioqnib');
    if (!sources.length) sources = document.querySelectorAll('li.h7wxwc');
    for (const li of sources) out.push(goto(li.querySelector('a.vIWmYe') || first(li)));
  }
  return out.filter(Boolean);
}"""
# True once the AI Overview's text length held still for ``ms``. With no
# overview it is true at once, unless ``late`` (page 1 of a plain query, where
# one may still attach): then its absence must hold still too.
_AIO_SETTLED_JS = """([ms, late]) => {
  const box = document.querySelector('#m-x-content');
  if (!box && !late) return true;
  const len = box ? box.innerText.length : -1;
  const now = performance.now();
  const seen = window.__gsAioSeen;
  if (!seen || seen.len !== len) {
    window.__gsAioSeen = {len, since: now};
    return false;
  }
  return now - seen.since >= ms;
}"""

# Strip the DOM before it is serialized (GOOGLE_SEARCH_SHRINK_DOM=0 keeps it
# whole): a rendered SERP is 4-6 MB, mostly inline script, style, svg and
# data-URI images the parser never reads, and page.content() plus the parse
# took up to 2 s on it. Favicons (img.XNo5Ab) keep their data URI for
# includeIcons; other data images keep the node and lose only the src, so a
# lazy image's data-src survives. saveHtml returns this stripped DOM.
_SHRINK_DOM = os.getenv("GOOGLE_SEARCH_SHRINK_DOM", "1") != "0"
_SHRINK_JS = """() => {
  document.querySelectorAll('script, style, noscript, svg').forEach(n => n.remove());
  document.querySelectorAll("img[src^='data:']").forEach(img => {
    if (!img.classList.contains('XNo5Ab')) img.removeAttribute('src');
  });
}"""


async def _settle(page) -> None:
    """Wait until the SERP's JS has loaded and its organic results are attached.

    The load event comes first because PAA clicks fired before the page's JS
    was ready answered nothing (0 of 4 after a /sorry solve, whose SERP is a
    fresh document). Both waits are capped, so a page without organic results
    costs at most the caps; neither is ever a failure.
    """
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("load", timeout=_LOAD_TIMEOUT_MS)
    with contextlib.suppress(Exception):
        await page.wait_for_selector(
            _READY_SEL, state="attached", timeout=_READY_TIMEOUT_MS
        )


def _may_have_paa(url: str) -> bool:
    """Page 1 of a plain query: later pages and ``site:`` searches carry no PAA."""
    params = parse_qs(urlsplit(url).query)
    start = (params.get("start") or ["0"])[0]
    query = (params.get("q") or [""])[0]
    return start in ("", "0") and "site:" not in query


async def _answers_in(page, n: int, cap_ms: int) -> bool:
    """Whether each of the first ``n`` PAA pairs held an answer within the cap."""
    try:
        await page.wait_for_function(
            _PAA_ANSWERED_JS, arg=n, timeout=cap_ms, polling=100
        )
    except Exception:
        return False
    return True


async def _click_paa(page) -> tuple[list, list]:
    """Click the first PAA questions open; return (toggles, clicked ones).

    Forced clicks skip Playwright's actionability waits (they are still
    trusted input) but aim where the element is at that instant. Each
    expansion animates and pushes everything below it down, so the questions
    are clicked bottom first, and the AI Overview above them is opened after.
    """
    if _may_have_paa(page.url or "") and await page.query_selector("div.tF2Cxc"):
        with contextlib.suppress(Exception):  # no PAA on this page
            await page.wait_for_selector(
                _PAA_SEL, state="attached", timeout=_PAA_ATTACH_MS
            )
    toggles = (await page.query_selector_all(_PAA_TOGGLE_SEL))[:_PAA_EXPAND_LIMIT]
    clicked = []
    for toggle in reversed(toggles):
        try:
            await toggle.click(
                force=True, no_wait_after=True, timeout=_CLICK_TIMEOUT_MS
            )
            clicked.append(toggle)
        except Exception:  # stale handle/overlay; skip pair
            continue
    return toggles, clicked


async def _await_paa(page, toggles: list, clicked: list) -> None:
    """Wait for the clicked questions' answers, then for the appended ones.

    When the answers do not come, a toggle still collapsed was clicked before
    its handler was bound and gets one more click; one that did expand is
    never clicked again, since that would close it.
    """
    if not clicked:
        return
    if not await _answers_in(page, len(toggles), _PAA_ANSWER_CAP_MS):
        retried = 0
        for toggle in clicked:
            with contextlib.suppress(Exception):
                if await toggle.get_attribute("aria-expanded") == "false":
                    await toggle.click(
                        force=True, no_wait_after=True, timeout=_CLICK_TIMEOUT_MS
                    )
                    retried += 1
        if retried:
            await _answers_in(page, len(toggles), _PAA_RETRY_CAP_MS)
    with contextlib.suppress(Exception):  # cap reached: keep what attached
        await page.wait_for_function(
            _PAA_STABLE_JS,
            arg=_PAA_STABLE_MS,
            timeout=_PAA_GRACE_CAP_MS,
            polling=100,
        )


async def _click_show_more(page) -> bool:
    """Open the AI Overview's "Show more" clamp, when it is there."""
    try:
        more = await page.query_selector(_AIO_SHOW_MORE_SEL)
        if more:
            await more.click(timeout=_CLICK_TIMEOUT_MS)
            return True
    except Exception:  # clamp absent/detached; the collapsed text still parses
        pass
    return False


async def _await_overview(page) -> None:
    """Wait for the AI Overview's text to stop growing; capped, never fails."""
    late = _may_have_paa(page.url or "")
    with contextlib.suppress(Exception):  # cap reached: keep what streamed
        await page.wait_for_function(
            _AIO_SETTLED_JS,
            arg=[_AIO_STABLE_MS, late],
            timeout=_AIO_PROSE_CAP_MS,
            polling=100,
        )


async def _feed_links(page, sink: LinkSink | None, *, expanded: bool) -> None:
    """Hand the page's /goto hrefs to ``sink``; best-effort."""
    if sink is None:
        return
    try:
        sink.feed(await page.evaluate(_LINKS_JS, expanded) or [])
    except Exception as e:  # the parse-time resolution picks them up instead
        logger.debug("[google_search] link prefetch skipped: %s", e)


async def _expand_blocks_fast(page, sink: LinkSink | None = None) -> int:
    """Event-driven expansion: settle, open PAA and AIO, wait for their text."""
    await _settle(page)
    await _feed_links(page, sink, expanded=False)
    toggles: list = []
    opened: list = []
    try:
        toggles, opened = await _click_paa(page)
    except Exception as e:  # never fail the render over PAA
        logger.debug("[google_search] PAA expansion skipped: %s", e)
    more = await _click_show_more(page)
    try:
        await _await_paa(page, toggles, opened)
    except Exception as e:  # never fail the render over PAA
        logger.debug("[google_search] PAA answers skipped: %s", e)
    await _await_overview(page)
    if not more and await _click_show_more(page):
        # The overview attached after the PAA clicks; open its clamp now.
        more = True
        await _await_overview(page)
    return len(opened) + int(more)


async def _expand_blocks_legacy(page) -> int:
    """The network-idle-era expansion: actionability clicks, then a fixed wait."""
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
    return clicked


async def _expand_blocks(page, sink: LinkSink | None = None):
    """Click open the lazy SERP blocks so their content renders into the DOM.

    Runs inside the browser render (Playwright async API — the persistent
    session's ``page_action`` must be a coroutine). Two expansions:

    * AI Overview "Show more" (``ponytail:`` clicked unconditionally, so the
      full overview is always scraped and ``scrapeFullAiOverview`` needs no
      plumbing down here — a superset of the actor's gated behavior).
    * The initially-served People-Also-Ask questions (answers load on click).

    Both are free on pages without the block, and best-effort: a failed click
    just leaves that section collapsed rather than failing the render. A page
    still on /sorry is left alone (the fetch loop moves to the next IP), and AI
    Mode keeps the old path: its render already waited for network idle.
    The page's /goto links go to ``sink`` as they appear. Finally the DOM is
    shrunk before scrapling serializes it.
    """
    _t0 = time.perf_counter()
    if _captcha.on_sorry(page):
        return page
    if _FAST_SETTLE and "udm=50" not in (page.url or ""):
        clicked = await _expand_blocks_fast(page, sink)
    else:
        clicked = await _expand_blocks_legacy(page)
    await _feed_links(page, sink, expanded=True)
    if _SHRINK_DOM:
        with contextlib.suppress(Exception):  # an unshrunk page still parses
            await page.evaluate(_SHRINK_JS)
    logger.info(
        "[google_search][perf] expand_ms=%.0f clicked=%d",
        (time.perf_counter() - _t0) * 1000,
        clicked,
    )
    return page


def _make_page_setup(proxy: str | None):
    """Per-fetch ``page_setup``: seed consent + any cached exemption for this IP."""

    async def page_setup(page):
        jar = list(_CONSENT_CTX)
        cached = _exemption_jar.get(proxy or "")
        if cached:
            jar += cached
        with contextlib.suppress(Exception):
            await page.context.add_cookies(jar)

    return page_setup


def _make_page_action(proxy: str | None, cfg, sink: LinkSink | None = None):
    """Per-fetch ``page_action``: solve the /sorry wall if hit, then expand blocks.

    Overrides the session default (:func:`_expand_blocks`) so it must still call
    it afterwards. On a successful solve the resulting ``GOOGLE_ABUSE_EXEMPTION``
    cookie is cached against this sticky proxy for reuse. ``cfg`` None skips
    the solve (no solver wired); ``sink`` takes the page's /goto links.
    """

    async def page_action(page):
        if (
            cfg is not None
            and _captcha.on_sorry(page)
            and await _captcha.solve_sorry(page, proxy, cfg)
        ):
            _exemption_jar[proxy or ""] = await _captcha.exemption_cookies(page)
        return await _expand_blocks(page, sink)

    return page_action


# Firefox-on-Android UA to make Google serve its mobile lightweight layout.
# ponytail: the engine underneath is patchright's *Chromium*, so this UA lies
# about the engine — but empirically it's what gets the mobile layout served
# without tripping Google's wall. A Chrome-on-Android UA (the "coherent"
# choice) gets 429-walled on every IP, so don't switch it back without a live
# mobile e2e proving the layout still loads.
_MOBILE_UA = "Mozilla/5.0 (Android 14; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0"
_MOBILE_VIEWPORT = {"width": 412, "height": 915}


# All browser work runs on the shared subprocess-capable loop (see
# proprietary.scraping.browser_loop).
# This also keeps the persistent AsyncStealthySession (and its async
# page_action) intact — the sync-fetcher-in-a-thread pattern would tear down
# the browser on every fetch.

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
# several scrape runs overlap). The pool and this gate are sized together
# (the session's max_pages is set from this): the gate queues excess renders
# instead of tripping the pool.
#
# This is THE throughput lever: per-process ceiling = this / warm-render-secs
# (≈ 4/14 s ≈ 17 SERP/min at the default). Renders drop images/fonts/media
# (`disable_resources`), so a single Chromium can hold well more than 4 text
# contexts — raise this (env) to trade RAM/CPU for throughput before adding
# processes. e.g. 16 → ~68/min/process, so ~8 processes cover 500/min.
_MAX_CONCURRENT_PAGES = int(os.getenv("GOOGLE_SEARCH_MAX_CONCURRENT_PAGES", "4"))
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
            # The page_action settles on the results themselves instead.
            "network_idle": not _FAST_SETTLE,
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


async def _render_on_loop(
    url: str, proxy: str | None, mobile: bool, sink: LinkSink | None = None
):
    async with _render_gate:
        session = await _get_session(mobile)
        _inflight[session] = _inflight.get(session, 0) + 1
        try:
            kwargs: dict = {}
            # Drop image/font/media/stylesheet requests: the SERP DOM we parse is
            # text/attribute-only, so these are dead weight (a warm render moved
            # ~2-7 MB per page) that also keeps `network_idle` from settling.
            # AI Mode streams its answer into the DOM, so leave its resources on
            # (dropping websockets/media can starve the stream) — detected by the
            # udm=50 marker its URL always carries.
            if "udm=50" not in url:
                kwargs["disable_resources"] = True
            else:
                # The AI Mode answer streams in; network idle is its settle.
                kwargs["network_idle"] = True
            # Only wire the solver when it's configured AND still viable this
            # process; otherwise the session's default page_action (expand-only)
            # runs and the stealth tier is unchanged.
            if proxy and captcha_enabled() and not _captcha.solver_latched():
                cfg = get_captcha_config()
                kwargs["page_setup"] = _make_page_setup(proxy)
                kwargs["page_action"] = _make_page_action(proxy, cfg, sink)
            elif sink is not None:
                kwargs["page_action"] = _make_page_action(proxy, None, sink)
            return await session.fetch(url, proxy=proxy, **kwargs)
        finally:
            _inflight[session] -= 1
            if not _inflight[session]:
                del _inflight[session]
                if session in _doomed:
                    _doomed.discard(session)
                    with contextlib.suppress(Exception):
                        await session.close()


async def _render(
    url: str, proxy: str | None, mobile: bool = False, sink: LinkSink | None = None
):
    """Headless render of a SERP on the shared browser (fresh proxy context).

    The actual browser work is marshalled onto the dedicated subprocess-capable
    loop (see :func:`_get_browser_loop`); this coroutine just awaits it from
    the caller's loop.
    """
    return await _in_browser_loop(_render_on_loop(url, proxy, mobile, sink))


async def warm_browser() -> None:
    """Launch the desktop browser now (GS-8): no context, no proxy, no credit."""
    if AsyncStealthySession is None:
        return
    lifecycle.at_shutdown(close_sessions)
    await _in_browser_loop(_get_session(False))


def render_slots() -> int:
    """Renders one call may run at once without vetting IPs it does not need.

    Follows the warm pool's free slots (each warm IP takes
    ``_WARM_IP_MAX_CONCURRENCY`` renders, less those other calls hold), at most
    the render gate: a burst queues for warm IPs instead of growing the pool
    through fresh vets that may need a paid solve. With no free warm slot it is
    1: two queries on a cold pool each vetted a fresh IP and both paid a /sorry
    solve (24.8 s, 2 solves), where one after the other the second page reuses
    the first one's IP.
    """
    with _pool_lock:
        free = sum(
            max(0, _WARM_IP_MAX_CONCURRENCY - _pool_inflight.get(url, 0))
            for url in _pool
        )
    return max(1, min(_MAX_CONCURRENT_PAGES, free))


async def fetch_serp_html(url: str, *, mobile: bool = False) -> str | None:
    """Return fully-rendered SERP HTML for ``url``, or ``None`` if unobtainable.

    Renders on a **warm sticky-IP pool**: it reuses an already-solved IP under
    its soft concurrency cap (spreading concurrent renders across the pool),
    grows the pool by vetting+solving a fresh IP when it's below target, and
    applies backpressure (a short wait) when the pool is full and busy rather
    than burning an extra solve. Retries walled IPs until real results land or
    the per-fetch deadline / IP budget runs out. Requires the browser tier —
    without it we cannot get JS-built results. ``mobile`` renders with a phone
    UA/viewport (the ``mobileResults`` input).
    """
    if AsyncStealthySession is None:
        logger.error("[google_search] browser tier unavailable; cannot render SERPs")
        return None
    lifecycle.at_shutdown(close_sessions)
    sink = link_sink.get()

    base = get_proxy_url()
    if not base:
        # No proxy configured: a single direct render, no pool bookkeeping.
        with contextlib.suppress(Exception):
            page = await _render(url, None, mobile=mobile, sink=sink)
            html = page.html_content or ""
            if page.status == 200 and _has_results(html):
                return html
        if sink is not None:
            sink.discard()
        logger.warning("[google_search] gave up on %s (unproxied single render)", url)
        return None

    deadline = time.monotonic() + _FETCH_DEADLINE_S
    ips_tried = 0
    while time.monotonic() < deadline and ips_tried < _MAX_IP_ATTEMPTS:
        action, proxy = _pool_take()
        if action == "wait":
            # Pool full and every IP busy: wait for a warm slot instead of
            # solving a fresh IP. The render gate drains continuously, so a slot
            # frees shortly; this is the queue that bounds solves to ~pool size.
            await asyncio.sleep(_POOL_WAIT_S)
            continue
        solved_fresh = False
        vet_ms = 0.0
        if action == "grow":
            # Before paying for a solve, try to adopt an IP another process
            # already solved (fleet-shared exemption). Only if none is available
            # do we vet a fresh IP and solve on it ourselves.
            try:
                adopted = await _store.adopt(set(_pool))
                if adopted is None:
                    await _stage("vetting fresh IPs")
                    vt = time.perf_counter()
                    proxy = await _vet_fresh_ip(url)
                    vet_ms = (time.perf_counter() - vt) * 1000
            except BaseException:
                # Cancelled (a host /cancel, or a sibling page failed): give the
                # reserved slot back, or it counts against the pool for good.
                _pool_abort_grow()
                raise
            if adopted is not None:
                proxy, cookies = adopted
                _exemption_jar[proxy] = cookies
                _pool_adopt(proxy)
            else:
                ips_tried += _VET_CONCURRENCY
                if proxy is None:
                    _pool_abort_grow()
                    logger.debug("[google_search] vetting round: all IPs walled")
                    await asyncio.sleep(_WALLED_ROUND_BACKOFF_S)
                    continue
                _pool_bind_fresh(proxy)
                solved_fresh = True
        try:
            await _stage("rendering on a fresh IP" if solved_fresh else "rendering")
            started = time.perf_counter()
            page = await _render(url, proxy, mobile=mobile, sink=sink)
        except asyncio.CancelledError:
            # Release the hold, or two leaked holds retire a warm IP for good.
            _pool_settle(proxy, good=None, grew=solved_fresh)
            raise
        except Exception as e:
            # Renders on a walled IP still return HTML; an exception means the
            # browser side is broken, so relaunch it rather than limp along.
            # repr(), not str(): e.g. NotImplementedError stringifies to "".
            logger.warning("[google_search] render failed: %r", e)
            if sink is not None:
                sink.discard()
            _pool_settle(proxy, good=False, grew=solved_fresh)
            await _store.evict(proxy)
            await _drop_session(mobile)
            continue
        fetch_ms = (time.perf_counter() - started) * 1000
        html = page.html_content or ""
        good = page.status == 200 and _has_results(html)
        _pool_settle(proxy, good=good, grew=solved_fresh)
        logger.info(
            "[google_search][perf] status=%s bytes=%d has_results=%s vet_ms=%.0f render_ms=%.0f from_pool=%s pool=%d",
            page.status,
            len(html),
            good,
            vet_ms,
            fetch_ms,
            not solved_fresh,
            len(_pool),
        )
        if good:
            # Share a freshly-solved IP with the fleet; a walled IP is poison,
            # so make sure no process keeps its stale exemption.
            if solved_fresh and _exemption_jar.get(proxy):
                await _store.publish(proxy, _exemption_jar[proxy])
            return html
        if sink is not None:
            sink.discard()
        await _stage("walled; trying another IP")
        await _store.evict(proxy)
    logger.warning(
        "[google_search] gave up on %s (deadline/%d-IP budget)", url, _MAX_IP_ATTEMPTS
    )
    return None
