"""One page's text: a fetch ladder that escalates until a tier yields usable content.

1. Static HTTP on the shared fail-fast transport: TLS-impersonated, no browser.
2. A page in the shared browser pool, on a sticky exit: for JS-rendered pages.
3. Scrapling StealthyFetcher: anti-bot browser, Cloudflare and captcha solving.

Trafilatura turns HTML into markdown. Every tier ends in the same ``CrawlOutcome``.
"""

import asyncio
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urldefrag

import trafilatura
import validators
from htmldate import find_date
from lxml import html as lxml_html
from markdownify import markdownify
from scrapling.engines.toolbelt import is_proxy_error
from scrapling.fetchers import AsyncFetcher, DynamicFetcher, StealthyFetcher
from trafilatura.utils import load_html

from proprietary.scraping import browser_pool, http, sessions, settle
from proprietary.scraping.browser_loop import in_browser_loop
from proprietary.scraping.browser_pool import LaunchProfile
from proprietary.scraping.captcha import captcha_enabled, get_captcha_config
from proprietary.scraping.proxy import get_active_provider, get_proxy_url
from proprietary.web_crawl.captcha import build_captcha_page_action
from proprietary.web_crawl.classifier import (
    CHALLENGE_TYPES,
    BlockType,
    classify_block,
    is_interstitial,
)
from proprietary.web_crawl.contacts import Contacts, extract_contacts
from proprietary.web_crawl.net_guard import is_publicly_routable
from proprietary.web_crawl.stealth import (
    StealthConfig,
    build_stealthy_kwargs,
    get_stealth_config,
    location_to_locale_timezone,
)
from proprietary.web_crawl.url_policy import extract_links, link_inventory

logger = logging.getLogger(__name__)

# Prefix for performance/timing log lines so they are easy to grep/filter.
_PERF = "[webcrawler][perf]"


def _switch_on(name: str) -> bool:
    """Kill switch: ``<name>=0`` in the environment restores the old path."""
    return os.environ.get(name, "1").strip() != "0"


# WEB_CRAWL_STATUS_ROUTING=0: every HTTP error and challenge walks the whole
# ladder again, and browser tiers accept any status, as before.
_ROUTING_SWITCH = "WEB_CRAWL_STATUS_ROUTING"
# WEB_CRAWL_HTML_CAP=0: extraction reads the whole document again.
_HTML_CAP_SWITCH = "WEB_CRAWL_HTML_CAP"
# WEB_CRAWL_RAW_STATIC=0: the static tier goes back to Scrapling's AsyncFetcher.
_RAW_STATIC_SWITCH = "WEB_CRAWL_RAW_STATIC"
# WEB_CRAWL_BROWSER_POOL=0: the dynamic tier launches its own browser again.
_POOL_SWITCH = "WEB_CRAWL_BROWSER_POOL"

_PLUGIN = "web-crawl"
# Browser escalations at once for this plugin, across every call: a depth
# crawl's static fetches fan out, its renders must not.
browser_pool.set_plugin_cap(_PLUGIN, 2)
# Browsers launched outside the pool at once (the stealth tier, and the dynamic
# tier with the pool off), across every call: each is its own Chromium and
# driver, and a stealth page may start a paid captcha solve.
_LAUNCH_CAP = 2
_launch_gate: asyncio.Semaphore | None = None


async def _gated_launch[T](launch: Callable[[], Awaitable[T]]) -> T:
    """``launch()`` once a launch slot is free; awaited on the browser loop."""
    global _launch_gate
    # Made on first use, so it belongs to the one loop every launch runs on.
    if _launch_gate is None:
        _launch_gate = asyncio.Semaphore(_LAUNCH_CAP)
    async with _launch_gate:
        return await launch()


def is_pool_backed() -> bool:
    """True when each proxy URL is a different exit, so re-running a tier rotates it.

    Neither provider here is (both rotate server-side), so no tier is retried today.
    """
    return bool(getattr(get_active_provider(), "is_pool_backed", False))


# Thin-page (JS-shell) escalation: a static fetch can "succeed" on an SPA that
# server-renders only a hero paragraph and hydrates the real content client-side
# (a16z.com/team: 4.2MB of HTML -> 597 chars extracted), so success alone must
# not stop the ladder. Calibrated on live pages (probe_thin_calibration): true
# shells shipped >=3.4MB with <0.05% text, while every healthy page was under
# ~650KB — so require BOTH a huge document and near-empty extraction.
# ponytail: ~150KB semi-shells (ycombinator.com/people) stay on static; their
# server-rendered link records still carry the content. Upgrade path: DOM
# hydration-marker sniffing instead of size thresholds.
_JS_SHELL_MIN_HTML_BYTES = 1_000_000
_JS_SHELL_MAX_CONTENT_CHARS = 2_500


def looks_like_js_shell(html_len: int, content_len: int) -> bool:
    """True when a static fetch smells like an unhydrated SPA shell."""
    return (
        html_len >= _JS_SHELL_MIN_HTML_BYTES
        and content_len < _JS_SHELL_MAX_CONTENT_CHARS
    )


# Lossy-extraction repair: trafilatura's main-content detection drops div-grid
# pricing cards / stat tables as "boilerplate" (seen live: duplicati.com/pricing
# kept 15% of visible text, goauthentik.io/pricing 0 of 5 currency figures while
# every price sat in the static DOM). Currency amounts are the one token class
# that is (a) trivially detectable, (b) never navigation chrome, and (c) the
# payload of exactly the pages agents ask for (pricing/plans). So: if the raw
# DOM shows a currency amount that the markdown lost, re-extract with
# favor_recall; if still lost, fall back to sanitized markdownify of the whole
# body (bounded — callers truncate via maxLength anyway).
# Covers $ € £ ¥ ₹ ₩ ₪ ₫ ₴ ₦ ₱ ฿ plus ISO codes like "USD 49"/"49 EUR" so the
# trigger is country-agnostic, and amounts-before-symbol ("49€", French/German).
_CURRENCY_AMOUNT_RE = re.compile(
    r"[$€£¥₹₩₪₫₴₦₱฿]\s?\d"
    r"|\d\s?[$€£¥₹₩₪₫₴₦₱฿]"
    r"|\b(USD|EUR|GBP|JPY|CNY|INR|BRL|MXN|CAD|AUD|CHF|KRW|SEK|NOK|DKK|PLN)\s?\d"
    r"|\d\s?(USD|EUR|GBP|JPY|CNY|INR|BRL|MXN|CAD|AUD|CHF|KRW|SEK|NOK|DKK|PLN)\b",
    re.IGNORECASE,
)

_STRIP_XPATH = (
    "//script | //style | //noscript | //template | //svg | //iframe | //head"
)


def _own_tree(page: Any) -> Any:
    """A tree the caller may change: ``page`` parsed, or a copy of a parsed one."""
    if isinstance(page, str):
        return lxml_html.fromstring(page)
    return deepcopy(page)


def _visible_text(page: Any) -> str:
    """Text of the DOM minus script/style — what a reader actually sees."""
    root = _own_tree(page)
    for bad in root.xpath(_STRIP_XPATH):
        bad.getparent().remove(bad)
    return " ".join(" ".join(root.itertext()).split())


def dropped_currency_amounts(page: Any, markdown: str) -> bool:
    """True when the visible DOM has currency figures but the markdown has none.

    ``page`` is HTML or a parsed tree (left unchanged).
    """
    if _CURRENCY_AMOUNT_RE.search(markdown):
        return False
    try:
        return bool(_CURRENCY_AMOUNT_RE.search(_visible_text(page)))
    except Exception:
        return False


def markdown_of_whole_body(page: Any) -> str | None:
    """Sanitized markdownify of the full DOM — recall 100%, precision be damned.

    Last resort when main-content extraction provably dropped the payload:
    nav/footer noise is acceptable, silently missing prices is not. ``page``
    is HTML or a parsed tree (left unchanged).
    """
    try:
        root = _own_tree(page)
        for bad in root.xpath(_STRIP_XPATH):
            bad.getparent().remove(bad)
        md = markdownify(lxml_html.tostring(root, encoding="unicode"))
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md or None
    except Exception:
        return None


# Extraction cost grows faster than page size (a 7.3 MB changelog took 17-25 s
# to keep 3000 chars). Past this cap the tail cannot reach the output; a 1 MB
# floor kept the first 50,000 chars identical on every sampled page.
_HTML_CAP_FLOOR = 1_000_000
_HTML_CAP_PER_OUTPUT_CHAR = 20
# Challenge markers sit near the top of a wall page; scanning the head is enough.
_CLASSIFY_HEAD_CHARS = 65_536
# Footer contacts sit at the end, past the cap on a huge page.
_CONTACTS_TAIL_CHARS = 65_536


def cap_html(raw_html: str, max_length: int | None) -> str:
    """``raw_html`` cut at the last tag end before the cap, when it is longer."""
    cap = max(_HTML_CAP_FLOOR, _HTML_CAP_PER_OUTPUT_CHAR * (max_length or 0))
    if len(raw_html) <= cap or not _switch_on(_HTML_CAP_SWITCH):
        return raw_html
    cut = raw_html.rfind(">", 0, cap)
    return raw_html[: cut + 1] if cut > 0 else raw_html[:cap]


# Sphinx/MkDocs/anchor.js permalinks: a pilcrow glued onto every heading and title.
_PERMALINK_XPATH = (
    "//a[contains(concat(' ', normalize-space(@class), ' '), ' headerlink ')]"
    " | //a[contains(concat(' ', normalize-space(@class), ' '), ' anchorjs-link ')]"
    " | //a[@aria-hidden='true'][starts-with(@href, '#')]"
)
_PERMALINK_TEXTS = frozenset({"", "\u00b6", "#", "\u00a7", "\U0001f517"})


def _strip_permalinks(tree: Any) -> None:
    """Drop heading permalink anchors, keeping the text that follows them."""
    for anchor in tree.xpath(_PERMALINK_XPATH):
        if anchor.text_content().strip() in _PERMALINK_TEXTS:
            anchor.drop_tree()


def _date_config(*, extensive: bool = False) -> dict[str, Any]:
    """The page's latest date, from its markup only: the default picks the oldest
    plausible date on the page (a 2026 release-notes page read as 2011).

    ``extensive`` also reads the text ("Last updated on ..."); asked only of a
    page whose markup has no date, as the text of a changelog is all dates.
    """
    return {
        "original_date": False,
        "extensive_search": extensive,
        "max_date": datetime.now().astimezone().strftime("%Y-%m-%d"),
    }


# Links kept per page by default; the rest are counted.
DEFAULT_MAX_LINKS = 200


@dataclass(frozen=True)
class PageLimits:
    """What a call keeps of each page; extraction skips work on what it drops."""

    max_length: int | None = None
    max_links: int = DEFAULT_MAX_LINKS


# Statuses a bot wall or the proxy answers with: another tier may still get
# through, on another exit.
_WALL_STATUSES = frozenset({401, 403, 407, 429, 503})
# A CDN's or gateway's passing failure (Cloudflare's 52x included): a later
# try may get the page. Any other 4xx/5xx is the site's own answer.
_RETRYABLE_STATUSES = _WALL_STATUSES | {502, 504, *range(520, 527)}
# A real error page ("Page not found" with the site's navigation) is bigger
# than this; a stub this small may be a gate that only browsers pass.
_ERROR_PAGE_MIN_CHARS = 2048
# Under this much text, a page with interstitial markers is the wall itself.
_CHALLENGE_MAX_CONTENT_CHARS = 1000


class HttpStatusError(Exception):
    """The site answered with a definitive HTTP error: no other tier would read the page."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


def _definitive_status(status: int | None, block_type: BlockType) -> bool:
    """A 4xx/5xx the site itself gave, with no sign of a bot wall."""
    return (
        status is not None
        and status >= 400
        and status not in _RETRYABLE_STATUSES
        and block_type not in CHALLENGE_TYPES
        and block_type is not BlockType.RATE_LIMITED
    )


def _reads_as_error_page(html: str) -> bool:
    """An error page with text of its own; a JS stub that a browser would fill has none."""
    if len(html) < _ERROR_PAGE_MIN_CHARS:
        return False
    try:
        return bool(trafilatura.extract(cap_html(html, None), fast=True))
    except Exception:
        return False


# Auto-scroll bounds for the browser tiers. JS directories/feeds lazy-load on
# scroll, so the initial render misses most items (e.g. YC's batch directory
# shows 40 of 100+ companies). The round cap keeps endless feeds (social
# timelines) from holding a fetch hostage. A page no taller than the window
# is not scrolled; a lazy loader gets two settle waits to add something.
_SCROLL_MAX_ROUNDS = 8
_SCROLL_SETTLE_MS = 400
_SCROLL_STILL_ROUNDS = 2


async def scroll_to_bottom(page: Any) -> Any:
    """``page_action`` that scrolls until the document height stops growing.

    ponytail: jumps straight to the bottom each round, which is enough for
    sentinel-based infinite scroll (Algolia et al.); lazy loaders keyed to
    intersection of mid-page elements would need viewport-sized steps. Errors
    mid-scroll keep whatever is already rendered instead of failing the fetch.
    """
    try:
        last_height = await page.evaluate("document.body.scrollHeight")
        viewport = await page.evaluate("window.innerHeight")
        if not last_height or (viewport and last_height <= viewport):
            return page
        still = 0
        for _ in range(_SCROLL_MAX_ROUNDS):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(_SCROLL_SETTLE_MS)
            height = await page.evaluate("document.body.scrollHeight")
            if height and height > last_height:
                last_height, still = height, 0
                continue
            still += 1
            if still >= _SCROLL_STILL_ROUNDS:
                break
    except Exception as exc:
        logger.debug("[webcrawler] auto-scroll aborted: %s", exc)
    return page


# Connect (proxy CONNECT and TLS included), then the whole request. Scrapling's
# 20 s, with its retries, let a dead host hold the static tier for a minute.
_STATIC_TIMEOUT = (5.0, 10.0)
# A bad exit, not the site: one more try draws a fresh one.
_STATIC_ATTEMPTS = 2
_EXIT_ERRORS = frozenset({"ProxyError", "ConnectionError"})
# A timeout this long hit after the connect phase: the site is slow, and the
# same budget again would only delay the browser.
_CONNECT_TIMEOUT_SLACK_MS = 1000


def _bad_exit(exc: http.TransportError) -> bool:
    """The exit failed us (a refused tunnel, a connect that never finished)."""
    if exc.kind == "Timeout":
        connect_ms = _STATIC_TIMEOUT[0] * 1000
        return exc.elapsed_ms < connect_ms + _CONNECT_TIMEOUT_SLACK_MS
    return exc.kind in _EXIT_ERRORS


# The dynamic tier's page timeout bounds the DOMContentLoaded wait; a page
# that never goes network-idle is read once the idle cap runs out.
_DYNAMIC_TIMEOUT_MS = 15_000
_IDLE_CAP_MS = 3_000


@dataclass(frozen=True)
class _Fetched:
    """A page as a tier got it: its status, the URL it ended on, and its HTML."""

    status: int | None
    url: str | None
    html: str


def _static_blocked(response: http.RawResponse) -> bool:
    """A wall, for the transport's perf line (the block-rate count)."""
    return (
        http.default_blocked(response)
        or response.status == 503
        or response.headers.get("cf-mitigated") == "challenge"
    )


async def _fetch_static(url: str) -> _Fetched:
    """One static GET on a fresh exit, tried once more when the exit failed."""
    if not _switch_on(_RAW_STATIC_SWITCH):
        page = await AsyncFetcher.get(
            url,
            stealthy_headers=True,
            impersonate="chrome",
            proxy=get_proxy_url(),
            timeout=20,
        )
        return _Fetched(
            getattr(page, "status", None),
            getattr(page, "url", None),
            page.html_content or "",
        )
    attempt = 0
    while True:
        try:
            # One-off: each attempt opens its own tunnel, so a new gateway IP.
            # The Google referer is the one header Scrapling's stealthy_headers
            # added; the transport sends it by default.
            response = await http.request(
                "GET",
                url,
                plugin=_PLUGIN,
                stage="static",
                proxy=sessions.Exit().proxy_url(),
                timeout=_STATIC_TIMEOUT,
                attempt=attempt,
                is_blocked=_static_blocked,
            )
        except http.TransportError as exc:
            attempt += 1
            if not _bad_exit(exc) or attempt >= _STATIC_ATTEMPTS:
                raise
            continue
        # Decoding megabytes is CPU work: off the loop.
        html = await asyncio.to_thread(response.text)
        return _Fetched(response.status, response.url, html)


def _launch_profile(cfg: StealthConfig) -> tuple[LaunchProfile, dict[str, Any]]:
    """The pooled browser for the launch-level stealth levers, and its context options."""
    locale = timezone_id = None
    if cfg.geoip_match_enabled:
        locale, timezone_id = location_to_locale_timezone(cfg.proxy_location)
    profile = LaunchProfile(
        block_webrtc=cfg.block_webrtc,
        hide_canvas=cfg.hide_canvas,
        dns_over_https=cfg.dns_over_https,
        locale=locale,
    )
    return profile, ({"timezone_id": timezone_id} if timezone_id else {})


def _lease() -> sessions.Exit:
    # One IP for the whole page load: a browser hopping across a rotating
    # gateway's exits looks like a botnet. The pool gives the lease back.
    return sessions.lease_exit("wc")


async def _render_dynamic(url: str) -> _Fetched:
    """``url`` rendered in a pooled browser on a sticky exit; runs on the browser loop."""
    cfg = get_stealth_config()
    profile, context_options = _launch_profile(cfg)
    async with browser_pool.page(
        _PLUGIN,
        profile,
        proxy=_lease,
        context_options=context_options,
        timeout_ms=_DYNAMIC_TIMEOUT_MS,
    ) as pooled:
        landing = await settle.goto(
            pooled.page,
            url,
            wait_until="domcontentloaded",
            idle_cap_ms=_IDLE_CAP_MS,
            referer=http.GOOGLE if cfg.google_search else None,
        )
        await scroll_to_bottom(pooled.page)
        html = await settle.page_content(pooled.page)
        # The exit met a wall: quarantine it so the next page draws another.
        if landing.status in _WALL_STATUSES:
            pooled.burn(f"HTTP {landing.status}")
        elif is_interstitial(html[:_CLASSIFY_HEAD_CHARS]):
            pooled.burn("interstitial")
        status = landing.status or None
        if _left_by_script(landing, url, pooled.page.url):
            # An error document that sent the browser on (a 404.html SPA
            # fallback): the landing status is not the rendered page's.
            status = None
        return _Fetched(status, pooled.page.url, html)


def _left_by_script(landing: settle.Landing, url: str, page_url: str | None) -> bool:
    """The page moved on from an error document after it loaded."""
    if not landing.status or landing.status < 400 or not page_url:
        return False
    landed = getattr(landing.response, "url", None) or url
    return urldefrag(page_url)[0] != urldefrag(landed)[0]


def _miss(block_state: dict[str, Any], routing: bool) -> tuple[str, bool]:
    """Why a tier returned nothing, and whether it reached the page itself.

    An error status or a challenge wall is not the page: with routing on, a
    ladder that only ever met those ends FAILED rather than EMPTY.
    """
    status = block_state.get("status")
    if status is not None and status >= 400:
        return f"HTTP {status}", not routing
    if block_state.get("blocked"):
        return f"{block_state['block_type']} challenge page", not routing
    return "empty extraction", True


class CrawlOutcomeStatus(StrEnum):
    """Deterministic per-URL crawl result."""

    SUCCESS = "success"  # a tier returned usable extracted content
    EMPTY = "empty"  # fetched, but no usable content after ALL tiers
    FAILED = "failed"  # invalid URL or every tier errored / was unavailable


@dataclass
class CrawlOutcome:
    """``crawl_url``'s result. Captcha fields are set only by the stealth tier;
    ``block_type`` labels the last fetched page and never decides success.
    """

    status: CrawlOutcomeStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    tier: str | None = None
    captcha_attempts: int = 0
    captcha_solved: bool = False
    block_type: BlockType = BlockType.UNKNOWN


def _merge_contacts(first: Contacts, second: Contacts) -> Contacts:
    """``first`` plus what ``second`` adds, deduped case-insensitively in order."""

    def merged(a: list[str], b: list[str]) -> list[str]:
        seen = {value.lower() for value in a}
        return a + [value for value in b if value.lower() not in seen]

    return Contacts(
        emails=merged(first.emails, second.emails),
        phones=merged(first.phones, second.phones),
        socials=merged(first.socials, second.socials),
    )


class WebCrawlerConnector:
    """Class for crawling web pages and extracting content."""

    async def crawl_url(
        self,
        url: str,
        limits: PageLimits | None = None,
        on_tier: Callable[[str], Awaitable[None]] | None = None,
    ) -> CrawlOutcome:
        """Crawl one URL down the ladder. On ``SUCCESS``, ``result`` holds ``content``
        (markdown), ``metadata``, ``loaded_url``, ``links``, ``link_records``,
        ``links_total`` and ``contacts``. ``limits`` bounds what is kept per page;
        ``on_tier`` is awaited with each tier's name as it starts.
        """
        limits = limits or PageLimits()

        async def starting(tier: str) -> None:
            if on_tier is not None:
                with suppress(Exception):
                    await on_tier(tier)

        total_start = time.perf_counter()
        # Per call, not on ``self``, so concurrent crawls never share them.
        captcha_state: dict[str, Any] = {"attempts": 0, "solved": False}
        # ``status`` and ``blocked`` describe the page the last tier got.
        block_state: dict[str, Any] = {"block_type": BlockType.UNKNOWN}
        routing = _switch_on(_ROUTING_SWITCH)
        try:
            if not validators.url(url):
                return CrawlOutcome(
                    status=CrawlOutcomeStatus.FAILED,
                    error=f"Invalid URL: {url}",
                    block_type=block_state["block_type"],
                )

            # ``validators.url`` passes loopback and the cloud metadata endpoint;
            # resolving first keeps those from being fetched from inside the
            # host's network. DNS blocks, so it runs off the loop.
            if not await asyncio.to_thread(is_publicly_routable, url):
                return CrawlOutcome(
                    status=CrawlOutcomeStatus.FAILED,
                    error=f"Restricted URL (host is not publicly routable): {url}",
                    block_type=block_state["block_type"],
                )

            errors: list[str] = []
            # True once any tier fetched the page but extraction yielded nothing
            # (distinguishes EMPTY from FAILED, where every tier raised/was
            # unavailable or only reached an error or challenge page).
            reached_without_content = False
            # Static result tagged as a JS shell: escalate to the browser tiers
            # for the hydrated page, but keep it as a last-resort fallback.
            thin_static_result: dict[str, Any] | None = None
            # A plain browser meets the same anti-bot wall the static fetch hit.
            skip_dynamic = False

            # --- 1. Scrapling AsyncFetcher (fast static HTTP) ---
            tier_start = time.perf_counter()
            block_state.update(status=None, blocked=False)
            try:
                await starting("static fetch")
                logger.info(f"[webcrawler] Static fetch for: {url}")
                result = await self._run_tier_with_proxy_retry(
                    "scrapling-static",
                    lambda: self._crawl_with_async_fetcher(url, block_state, limits),
                )
                if result and result.pop("thin_static", False):
                    thin_static_result = result
                    errors.append(
                        "Scrapling static: JS-shell page (huge HTML, near-empty "
                        "extraction); escalating to browser"
                    )
                    self._log_tier_outcome(
                        "scrapling-static", url, tier_start, "thin_shell"
                    )
                elif result:
                    self._log_tier_outcome(
                        "scrapling-static", url, tier_start, "success"
                    )
                    self._log_total(url, "scrapling-static", total_start)
                    return CrawlOutcome(
                        status=CrawlOutcomeStatus.SUCCESS,
                        result=result,
                        tier="scrapling-static",
                        block_type=block_state["block_type"],
                    )
                else:
                    miss, reached = _miss(block_state, routing)
                    reached_without_content |= reached
                    errors.append(f"Scrapling static: {miss}")
                    skip_dynamic = (
                        routing
                        and not reached
                        and block_state["block_type"] in CHALLENGE_TYPES
                    )
                    self._log_tier_outcome(
                        "scrapling-static",
                        url,
                        tier_start,
                        "skip_to_stealth" if skip_dynamic else "empty",
                    )
            except HttpStatusError as exc:
                self._log_tier_outcome(
                    "scrapling-static", url, tier_start, "http_error"
                )
                return self._http_failure(
                    url, exc, total_start, captcha_state, block_state
                )
            except Exception as exc:
                errors.append(f"Scrapling static: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-static", url, tier_start, "error", exc
                )

            # --- 2. Scrapling DynamicFetcher (full browser) ---
            tier_start = time.perf_counter()
            block_state.update(status=None, blocked=False)
            try:
                if skip_dynamic:
                    errors.append(
                        f"Scrapling dynamic: skipped ({block_state['block_type']} wall)"
                    )
                else:
                    await starting("browser render")
                    logger.info(f"[webcrawler] Browser render for: {url}")
                    result = await self._run_tier_with_proxy_retry(
                        "scrapling-dynamic",
                        lambda: self._crawl_with_dynamic(url, block_state, limits),
                    )
                    if result:
                        self._log_tier_outcome(
                            "scrapling-dynamic", url, tier_start, "success"
                        )
                        self._log_total(url, "scrapling-dynamic", total_start)
                        return CrawlOutcome(
                            status=CrawlOutcomeStatus.SUCCESS,
                            result=result,
                            tier="scrapling-dynamic",
                            block_type=block_state["block_type"],
                        )
                    miss, reached = _miss(block_state, routing)
                    reached_without_content |= reached
                    errors.append(f"Scrapling dynamic: {miss}")
                    self._log_tier_outcome(
                        "scrapling-dynamic", url, tier_start, "empty"
                    )
            except HttpStatusError as exc:
                self._log_tier_outcome(
                    "scrapling-dynamic", url, tier_start, "http_error"
                )
                return self._http_failure(
                    url, exc, total_start, captcha_state, block_state
                )
            except NotImplementedError:
                errors.append(
                    "Scrapling dynamic: event loop does not support subprocesses "
                    "(common on Windows with uvicorn --reload)"
                )
                self._log_tier_outcome(
                    "scrapling-dynamic", url, tier_start, "unavailable"
                )
            except Exception as exc:
                errors.append(f"Scrapling dynamic: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-dynamic", url, tier_start, "error", exc
                )

            # --- 3. Scrapling StealthyFetcher (anti-bot, last resort) ---
            tier_start = time.perf_counter()
            block_state.update(status=None, blocked=False)
            try:
                await starting("stealth browser")
                logger.info(f"[webcrawler] Using Scrapling StealthyFetcher for: {url}")
                result = await self._run_tier_with_proxy_retry(
                    "scrapling-stealthy",
                    lambda: self._crawl_with_stealthy(
                        url, captcha_state, block_state, limits
                    ),
                )
                if result:
                    self._log_tier_outcome(
                        "scrapling-stealthy", url, tier_start, "success"
                    )
                    self._log_total(url, "scrapling-stealthy", total_start)
                    return CrawlOutcome(
                        status=CrawlOutcomeStatus.SUCCESS,
                        result=result,
                        tier="scrapling-stealthy",
                        captcha_attempts=captcha_state["attempts"],
                        captcha_solved=captcha_state["solved"],
                        block_type=block_state["block_type"],
                    )
                miss, reached = _miss(block_state, routing)
                reached_without_content |= reached
                errors.append(f"Scrapling stealthy: {miss}")
                self._log_tier_outcome("scrapling-stealthy", url, tier_start, "empty")
            except NotImplementedError:
                errors.append(
                    "Scrapling stealthy: event loop does not support subprocesses "
                    "(common on Windows with uvicorn --reload)"
                )
                self._log_tier_outcome(
                    "scrapling-stealthy", url, tier_start, "unavailable"
                )
            except Exception as exc:
                errors.append(f"Scrapling stealthy: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-stealthy", url, tier_start, "error", exc
                )

            # Browser tiers all failed/empty: the thin static extraction is
            # still real (partial) content — better than reporting nothing.
            if thin_static_result is not None:
                self._log_total(url, "scrapling-static-thin", total_start)
                return CrawlOutcome(
                    status=CrawlOutcomeStatus.SUCCESS,
                    result=thin_static_result,
                    tier="scrapling-static",
                    captcha_attempts=captcha_state["attempts"],
                    captcha_solved=captcha_state["solved"],
                    block_type=block_state["block_type"],
                )

            self._log_total(url, "none", total_start)
            if reached_without_content:
                return CrawlOutcome(
                    status=CrawlOutcomeStatus.EMPTY,
                    error=f"No content extracted for {url}. {'; '.join(errors)}",
                    captcha_attempts=captcha_state["attempts"],
                    captcha_solved=captcha_state["solved"],
                    block_type=block_state["block_type"],
                )
            return CrawlOutcome(
                status=CrawlOutcomeStatus.FAILED,
                error=f"All crawl methods failed for {url}. {'; '.join(errors)}",
                captcha_attempts=captcha_state["attempts"],
                captcha_solved=captcha_state["solved"],
                block_type=block_state["block_type"],
            )

        except Exception as e:
            self._log_total(url, "error", total_start)
            return CrawlOutcome(
                status=CrawlOutcomeStatus.FAILED,
                error=f"Error crawling URL {url}: {e!s}",
                captcha_attempts=captcha_state["attempts"],
                captcha_solved=captcha_state["solved"],
                block_type=block_state["block_type"],
            )

    def _http_failure(
        self,
        url: str,
        exc: HttpStatusError,
        total_start: float,
        captcha_state: dict[str, Any],
        block_state: dict[str, Any],
    ) -> CrawlOutcome:
        """The site's own error answer ends the ladder: no tier would do better."""
        self._log_total(url, "none", total_start)
        return CrawlOutcome(
            status=CrawlOutcomeStatus.FAILED,
            error=f"HTTP {exc.status} for {url}",
            captcha_attempts=captcha_state["attempts"],
            captcha_solved=captcha_state["solved"],
            block_type=block_state["block_type"],
        )

    async def _run_tier_with_proxy_retry(
        self,
        tier: str,
        attempt: Callable[[], Awaitable[dict[str, Any] | None]],
    ) -> dict[str, Any] | None:
        """Run one tier, retried once on a proxy error when a re-run draws another exit."""
        try:
            return await attempt()
        except Exception as exc:
            if is_proxy_error(exc) and is_pool_backed():
                logger.warning(
                    "%s tier=%s proxy error; rotating endpoint, retrying once: %s",
                    _PERF,
                    tier,
                    exc,
                )
                return await attempt()
            raise

    @staticmethod
    def _log_tier_outcome(
        tier: str,
        url: str,
        tier_start: float,
        outcome: str,
        exc: Exception | None = None,
    ) -> None:
        """Log how long a single tier took and how it ended."""
        elapsed_ms = (time.perf_counter() - tier_start) * 1000
        if outcome == "error":
            logger.warning(
                "%s tier=%s url=%s elapsed_ms=%.1f outcome=error error=%s",
                _PERF,
                tier,
                url,
                elapsed_ms,
                exc,
            )
        else:
            logger.info(
                "%s tier=%s url=%s elapsed_ms=%.1f outcome=%s",
                _PERF,
                tier,
                url,
                elapsed_ms,
                outcome,
            )

    @staticmethod
    def _log_total(url: str, selected: str, total_start: float) -> None:
        """Log the total time spent across all attempted tiers."""
        total_ms = (time.perf_counter() - total_start) * 1000
        logger.info(
            "%s url=%s selected=%s total_ms=%.1f",
            _PERF,
            url,
            selected,
            total_ms,
        )

    async def _crawl_with_async_fetcher(
        self,
        url: str,
        block_state: dict[str, Any] | None = None,
        limits: PageLimits | None = None,
    ) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's AsyncFetcher (static HTTP) + Trafilatura.

        AsyncFetcher is httpx/curl_cffi based and does not launch a browser
        subprocess, making it safe to call from any asyncio event loop. Returns
        ``None`` when Trafilatura cannot extract meaningful content (e.g. JS
        rendered SPAs) so the caller can fall through to the browser tiers.
        Raises ``HttpStatusError`` when the site answered with a real error page.
        """
        fetch_start = time.perf_counter()
        # Chrome's TLS ClientHello (JA3/JA4), not curl's, keeps the static
        # tier coherent with the browser tiers' UA.
        page = await _fetch_static(url)
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

        status = page.status
        if status is not None and status >= 400:
            html = page.html
            # This return skips _build_result; the 403/429 bot-gate would go unlabeled.
            block_type = classify_block(status, html[:_CLASSIFY_HEAD_CHARS])
            if block_state is not None:
                block_state["block_type"] = block_type
                block_state["status"] = status
            logger.info(
                "%s tier=scrapling-static url=%s fetch_ms=%.1f status=%s outcome=http_error",
                _PERF,
                url,
                fetch_ms,
                status,
            )
            # A "Page not found" page with text of its own is the site's
            # answer; a tiny or textless one may be a gate only browsers pass.
            if (
                _switch_on(_ROUTING_SWITCH)
                and _definitive_status(status, block_type)
                and await asyncio.to_thread(_reads_as_error_page, html)
            ):
                raise HttpStatusError(status)
            return None

        # Trafilatura is CPU-bound (100ms+ on large pages); off the loop.
        result = await asyncio.to_thread(
            self._build_result,
            page.html,
            url,
            "scrapling-static",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=status,
            block_state=block_state,
            loaded_url=page.url,
            limits=limits,
        )
        if result and looks_like_js_shell(
            len(page.html), len(result.get("content") or "")
        ):
            # Tag rather than drop: crawl_url escalates to the browser tiers but
            # keeps this as a fallback if they all fail (e.g. no subprocess
            # support on Windows dev loops).
            result["thin_static"] = True
        return result

    async def _crawl_with_dynamic(
        self,
        url: str,
        block_state: dict[str, Any] | None = None,
        limits: PageLimits | None = None,
    ) -> dict[str, Any] | None:
        """A full browser on the browser loop, which can launch it on any platform."""
        fetch_start = time.perf_counter()
        if _switch_on(_POOL_SWITCH):
            page = await browser_pool.run(lambda: _render_dynamic(url))
        else:
            fetched = await in_browser_loop(
                _gated_launch(
                    lambda: DynamicFetcher.async_fetch(
                        url,
                        headless=True,
                        network_idle=True,
                        timeout=30000,
                        proxy=get_proxy_url(),
                        page_action=scroll_to_bottom,
                    )
                )
            )
            page = _Fetched(
                getattr(fetched, "status", None),
                getattr(fetched, "url", None),
                fetched.html_content,
            )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        status = page.status
        result = await asyncio.to_thread(
            self._build_result,
            page.html,
            url,
            "scrapling-dynamic",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=status,
            block_state=block_state,
            loaded_url=page.url,
            limits=limits,
        )
        # The rendered page is the site's own error: stealth would get it too.
        if (
            result is None
            and block_state is not None
            and _switch_on(_ROUTING_SWITCH)
            and _definitive_status(status, block_state["block_type"])
        ):
            raise HttpStatusError(status)
        return result

    async def _crawl_with_stealthy(
        self,
        url: str,
        captcha_state: dict[str, Any] | None = None,
        block_state: dict[str, Any] | None = None,
        limits: PageLimits | None = None,
    ) -> dict[str, Any] | None:
        """The last-resort anti-bot browser; keeps the whole body as markdown when extraction is empty.

        ``captcha_state`` gets the captcha page_action's attempts and success.
        """
        fetch_start = time.perf_counter()
        # One proxy endpoint for the fetch and the solver: tokens are IP-bound.
        proxy = get_proxy_url()

        captcha_action = None
        if captcha_state is not None and captcha_enabled():
            captcha_action = build_captcha_page_action(
                captcha_state, proxy, get_captcha_config()
            )

        # Captcha first: scrolling a challenge interstitial is pointless.
        async def page_action(page: Any) -> Any:
            if captcha_action is not None:
                page = await captcha_action(page)
            return await scroll_to_bottom(page)

        # Scrapling runs solve_cloudflare before page_action, so Cloudflare is
        # cleared before the captcha injector looks.
        fetch_kwargs: dict[str, Any] = {
            "headless": True,
            "network_idle": True,
            "block_ads": True,
            "solve_cloudflare": True,
            "proxy": proxy,
        }
        fetch_kwargs.update(build_stealthy_kwargs(get_stealth_config()))
        fetch_kwargs["page_action"] = page_action
        page = await in_browser_loop(
            _gated_launch(lambda: StealthyFetcher.async_fetch(url, **fetch_kwargs))
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        return await asyncio.to_thread(
            self._build_result,
            page.html_content,
            url,
            "scrapling-stealthy",
            allow_raw_fallback=True,
            fetch_ms=fetch_ms,
            status=getattr(page, "status", None),
            block_state=block_state,
            loaded_url=getattr(page, "url", None),
            limits=limits,
        )

    def _build_result(
        self,
        raw_html: str | None,
        url: str,
        crawler_type: str,
        *,
        allow_raw_fallback: bool,
        fetch_ms: float | None = None,
        status: int | None = None,
        block_state: dict[str, Any] | None = None,
        loaded_url: str | None = None,
        limits: PageLimits | None = None,
    ) -> dict[str, Any] | None:
        """
        Extract markdown + metadata from raw HTML using Trafilatura.

        Args:
            raw_html: Raw HTML source from a fetcher.
            url: Original URL (used as the metadata source/title fallback).
            crawler_type: Identifier of the tier that produced the HTML.
            allow_raw_fallback: When True, return the whole body as markdown if
                Trafilatura cannot extract anything (used by the last-resort
                stealthy tier). When False, return ``None`` so the caller can
                fall through to the next tier.
            fetch_ms: Time spent fetching the page (for perf logging).
            status: HTTP status code returned by the fetcher.
            block_state: Gets the page's ``block_type``, and ``blocked`` when
                the page is a challenge wall.
            loaded_url: The URL the fetcher ended on after redirects; links
                resolve against it.
            limits: What the call keeps per page; the HTML is capped to match.

        Returns:
            Result dict (content/metadata/crawler_type/links) or ``None``.
        """
        limits = limits or PageLimits()
        routing = _switch_on(_ROUTING_SWITCH)
        # Before the early returns, so empty pages are labeled too; the last tier wins.
        block_type = classify_block(
            status, raw_html[:_CLASSIFY_HEAD_CHARS] if raw_html else raw_html
        )
        if block_state is not None:
            block_state["block_type"] = block_type
            block_state["status"] = status

        html_len = len(raw_html) if raw_html else 0

        if not raw_html or len(raw_html.strip()) == 0:
            self._log_build(
                crawler_type, url, fetch_ms, 0.0, status, html_len, 0, "empty_html"
            )
            return None

        # A browser renders error and challenge pages like any other: their
        # text is not the page asked for.
        if routing and status is not None and status >= 400:
            self._log_build(
                crawler_type, url, fetch_ms, 0.0, status, html_len, 0, "http_error"
            )
            return None

        page_url = loaded_url or url
        extract_start = time.perf_counter()
        html = cap_html(raw_html, limits.max_length)
        extracted_content: str | None = None
        tree = None

        # One parse feeds extraction, the currency check, links, contacts and
        # metadata; trafilatura copies the tree before it prunes it.
        try:
            tree = load_html(html)
        except Exception:
            tree = None
        if tree is not None:
            _strip_permalinks(tree)
            try:
                extracted_content = trafilatura.extract(
                    tree,
                    url=page_url,
                    output_format="markdown",
                    include_comments=False,
                    include_tables=True,
                    include_images=True,
                    include_links=True,
                )
                if extracted_content and len(extracted_content.strip()) == 0:
                    extracted_content = None
            except Exception:
                extracted_content = None

        # Repair chain for provably lossy extraction: trafilatura sometimes
        # classifies pricing cards / stat grids as boilerplate. If the DOM shows
        # currency amounts the markdown lost, retry with favor_recall, then fall
        # back to sanitized whole-body markdown. Guarded by the currency check
        # (a regex over the raw string first), so ordinary pages never pay for
        # a second extraction pass.
        if (
            extracted_content
            and _CURRENCY_AMOUNT_RE.search(html)
            and dropped_currency_amounts(tree, extracted_content)
        ):
            try:
                recall = trafilatura.extract(
                    tree,
                    url=page_url,
                    output_format="markdown",
                    include_comments=False,
                    include_tables=True,
                    include_images=True,
                    include_links=True,
                    favor_recall=True,
                )
            except Exception:
                recall = None
            if recall and _CURRENCY_AMOUNT_RE.search(recall):
                extracted_content = recall
            else:
                whole = markdown_of_whole_body(tree)
                if whole and _CURRENCY_AMOUNT_RE.search(whole):
                    extracted_content = whole
            logger.info(
                f"{_PERF} event=lossy_repair url={url} recovered="
                f"{bool(_CURRENCY_AMOUNT_RE.search(extracted_content))}"
            )

        content = extracted_content
        if not content and allow_raw_fallback:
            # Whole-body markdown, never the raw HTML: the field is markdown.
            content = markdown_of_whole_body(tree if tree is not None else html)

        extract_ms = (time.perf_counter() - extract_start) * 1000

        if not content:
            self._log_build(
                crawler_type,
                url,
                fetch_ms,
                extract_ms,
                status,
                html_len,
                0,
                "no_extraction",
            )
            return None

        # A wall's few words are not the page: let the ladder escalate.
        if (
            routing
            and len(content) < _CHALLENGE_MAX_CONTENT_CHARS
            and is_interstitial(raw_html[:_CLASSIFY_HEAD_CHARS])
        ):
            if block_state is not None:
                block_state["blocked"] = True
            self._log_build(
                crawler_type,
                url,
                fetch_ms,
                extract_ms,
                status,
                html_len,
                len(content),
                "challenge",
            )
            return None

        self._log_build(
            crawler_type,
            url,
            fetch_ms,
            extract_ms,
            status,
            html_len,
            len(content),
            "extracted" if extracted_content else "whole_body_fallback",
        )

        # The per-anchor inventory is agent output (anchor text is the raw
        # material for entity extraction), labeled only for the records kept.
        # The frontier for ``site_crawler.crawl_site`` is every link of the
        # whole document, even past the extraction cap.
        link_records, links_total = link_inventory(
            tree, page_url, max_records=limits.max_links
        )
        if html is raw_html and links_total <= limits.max_links:
            links = [
                r["url"] for r in link_records if r["kind"] not in ("email", "tel")
            ]
        else:
            links = extract_links(raw_html if html is not raw_html else tree, page_url)
        # Lead-gen signals harvested from raw HTML (footer/legal boilerplate
        # that Trafilatura strips from ``content``). A capped page's footer is
        # past the cap, so its tail's links are read too; the email scan, a
        # regex, reads the whole page.
        contacts = extract_contacts(html, root=tree, scan_text=raw_html)
        if html is not raw_html:
            contacts = _merge_contacts(
                contacts, extract_contacts(raw_html[-_CONTACTS_TAIL_CHARS:])
            )

        # Last: htmldate and the author search are the slowest part of it.
        metadata: dict[str, str] = {"source": url}
        try:
            trafilatura_metadata = trafilatura.extract_metadata(
                tree, default_url=page_url, date_config=_date_config()
            )
        except Exception:
            trafilatura_metadata = None
        if trafilatura_metadata:
            title = (trafilatura_metadata.title or "").rstrip("\u00b6 ").strip()
            if title:
                metadata["title"] = title
            if trafilatura_metadata.description:
                metadata["description"] = trafilatura_metadata.description
            if trafilatura_metadata.author:
                metadata["author"] = trafilatura_metadata.author
            if trafilatura_metadata.date:
                metadata["date"] = trafilatura_metadata.date
        if "date" not in metadata and tree is not None:
            # A docs page dates itself only in its footer text (20-60 ms).
            with suppress(Exception):
                date = find_date(tree, url=page_url, **_date_config(extensive=True))
                if date:
                    metadata["date"] = date
        metadata.setdefault("title", url)

        return {
            "content": content,
            "metadata": metadata,
            "crawler_type": crawler_type,
            "loaded_url": page_url,
            # Next-hop targets for ``site_crawler.crawl_site``; ignored by
            # single-URL callers.
            "links": links,
            "link_records": link_records,
            # The capped tree can hold fewer links than the whole frontier.
            "links_total": max(links_total, len(links)),
            # Dict form so callers can pass it straight through without
            # importing the dataclass.
            "contacts": contacts.as_dict(),
        }

    @staticmethod
    def _log_build(
        crawler_type: str,
        url: str,
        fetch_ms: float | None,
        extract_ms: float,
        status: int | None,
        html_len: int,
        content_len: int,
        outcome: str,
    ) -> None:
        """Emit a detailed perf line splitting fetch vs Trafilatura extraction."""
        fetch_repr = f"{fetch_ms:.1f}" if fetch_ms is not None else "n/a"
        logger.info(
            "%s tier=%s url=%s status=%s fetch_ms=%s extract_ms=%.1f "
            "html_len=%d content_len=%d outcome=%s",
            _PERF,
            crawler_type,
            url,
            status,
            fetch_repr,
            extract_ms,
            html_len,
            content_len,
            outcome,
        )
