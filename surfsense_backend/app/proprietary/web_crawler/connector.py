# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""
WebCrawler Connector Module

A single-framework (Scrapling) web crawler with Trafilatura for HTML -> markdown
extraction. Provides a unified interface for web scraping.

Fallback ladder (the ``FetchStrategy`` seam — see ``plans/backend/03a-crawler-core.md``):
  1. Scrapling AsyncFetcher    (fast static HTTP, TLS-impersonated, no subprocess)
  2. Scrapling DynamicFetcher  (full browser, run in a thread)
  3. Scrapling StealthyFetcher (patchright-Chromium anti-bot + Cloudflare solving,
                                run in a thread)

Every tier returns extracted content via the same ``CrawlOutcome`` contract, so
callers (indexer, chat tool, crawl billing) depend only on the outcome, never on
which tier produced it.
"""

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import trafilatura
import validators
from lxml import html as lxml_html
from markdownify import markdownify
from scrapling.engines.toolbelt import is_proxy_error
from scrapling.fetchers import AsyncFetcher, DynamicFetcher, StealthyFetcher

from app.proprietary.web_crawler.captcha import build_captcha_page_action
from app.proprietary.web_crawler.stealth import (
    build_stealthy_kwargs,
    get_stealth_config,
)
from app.proprietary.web_crawler.url_policy import extract_link_records
from app.utils.captcha import captcha_enabled, get_captcha_config
from app.utils.crawl import BlockType, classify_block, extract_contacts
from app.utils.proxy import get_proxy_url, is_pool_backed

logger = logging.getLogger(__name__)

# Prefix for performance/timing log lines so they are easy to grep/filter.
_PERF = "[webcrawler][perf]"

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

_STRIP_XPATH = "//script | //style | //noscript | //template | //svg | //iframe | //head"


def _visible_text(raw_html: str) -> str:
    """Text of the DOM minus script/style — what a reader actually sees."""
    root = lxml_html.fromstring(raw_html)
    for bad in root.xpath(_STRIP_XPATH):
        bad.getparent().remove(bad)
    return " ".join(" ".join(root.itertext()).split())


def dropped_currency_amounts(raw_html: str, markdown: str) -> bool:
    """True when the visible DOM has currency figures but the markdown has none."""
    if _CURRENCY_AMOUNT_RE.search(markdown):
        return False
    try:
        return bool(_CURRENCY_AMOUNT_RE.search(_visible_text(raw_html)))
    except Exception:
        return False


def markdown_of_whole_body(raw_html: str) -> str | None:
    """Sanitized markdownify of the full DOM — recall 100%, precision be damned.

    Last resort when main-content extraction provably dropped the payload:
    nav/footer noise is acceptable, silently missing prices is not.
    """
    try:
        root = lxml_html.fromstring(raw_html)
        for bad in root.xpath(_STRIP_XPATH):
            bad.getparent().remove(bad)
        md = markdownify(lxml_html.tostring(root, encoding="unicode"))
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md or None
    except Exception:
        return None


# Auto-scroll bounds for the browser tiers. JS directories/feeds lazy-load on
# scroll, so the initial render misses most items (e.g. YC's batch directory
# shows 40 of 100+ companies). The round cap keeps endless feeds (social
# timelines) from holding a billable fetch hostage; static-height pages exit
# after one no-growth check, costing a single settle wait.
_SCROLL_MAX_ROUNDS = 8
_SCROLL_SETTLE_MS = 700


def scroll_to_bottom(page: Any) -> Any:
    """``page_action`` that scrolls until the document height stops growing.

    ponytail: jumps straight to the bottom each round, which is enough for
    sentinel-based infinite scroll (Algolia et al.); lazy loaders keyed to
    intersection of mid-page elements would need viewport-sized steps. Errors
    mid-scroll keep whatever is already rendered instead of failing the fetch.
    """
    try:
        last_height = 0
        for _ in range(_SCROLL_MAX_ROUNDS):
            height = page.evaluate("document.body.scrollHeight")
            if not height or height <= last_height:
                break
            last_height = height
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(_SCROLL_SETTLE_MS)
    except Exception as exc:
        logger.debug("[webcrawler] auto-scroll aborted: %s", exc)
    return page


class CrawlOutcomeStatus(StrEnum):
    """Deterministic per-URL crawl result, single-sourcing the billable signal."""

    SUCCESS = "success"  # a tier returned usable extracted content
    EMPTY = "empty"  # fetched, but no usable content after ALL tiers
    FAILED = "failed"  # invalid URL or every tier errored / was unavailable


@dataclass
class CrawlOutcome:
    """Explicit ``crawl_url`` result shared by every caller.

    The **billable success predicate is single-sourced**:
    ``status == CrawlOutcomeStatus.SUCCESS`` (Phase 3c meters on it). Picking a
    dataclass over a tuple lets later subplans append fields without breaking
    callers (03e's block classifier can attach a ``block_type``).

    Phase 3d captcha fields are surfaced here so per-attempt billing can read
    them off the outcome regardless of crawl SUCCESS (the solver charges per
    *attempt*). They are populated only by the StealthyFetcher tier when captcha
    solving is enabled; every other path leaves the defaults (0 / False).

    Phase 3e ``block_type`` is purely *additive* telemetry: the block classifier
    labels the last fetched page (Cloudflare / captcha / DataDome / rate-limited
    / ...) for tuning + future escalation routing. It does NOT influence the
    billable ``SUCCESS`` predicate above.
    """

    status: CrawlOutcomeStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    tier: str | None = None
    captcha_attempts: int = 0
    captcha_solved: bool = False
    block_type: BlockType = BlockType.UNKNOWN


class WebCrawlerConnector:
    """Class for crawling web pages and extracting content."""

    async def crawl_url(self, url: str) -> CrawlOutcome:
        """
        Crawl a single URL and extract its content.

        Fallback ladder:
          1. Scrapling AsyncFetcher (fast static HTTP, TLS-impersonated)
          2. Scrapling DynamicFetcher (full browser, run in a thread)
          3. Scrapling StealthyFetcher (anti-bot stealth browser + Cloudflare
             solving, run in a thread)

        Args:
            url: URL to crawl

        Returns:
            A ``CrawlOutcome``. On ``SUCCESS``, ``result`` is a dict containing:
                - content: Extracted content (markdown)
                - metadata: Page metadata (title, description, etc.)
                - crawler_type: Identifier of the tier that produced the content
        """
        total_start = time.perf_counter()
        # Per-call captcha telemetry (03d). Mutated only by the StealthyFetcher
        # tier's page_action; stamped onto the returned outcome so per-attempt
        # billing can read it regardless of crawl SUCCESS. Per-call (not on
        # ``self``) => safe under concurrent ``crawl_url`` calls.
        captcha_state: dict[str, Any] = {"attempts": 0, "solved": False}
        # Per-call block-classifier telemetry (03e). ``_build_result`` (the one
        # place with raw_html + status) classifies each fetched page into here;
        # crawl_url stamps it onto every outcome. Additive only — never gates
        # SUCCESS. Per-call (not on ``self``) => concurrency-safe.
        block_state: dict[str, Any] = {"block_type": BlockType.UNKNOWN}
        try:
            if not validators.url(url):
                return CrawlOutcome(
                    status=CrawlOutcomeStatus.FAILED,
                    error=f"Invalid URL: {url}",
                    block_type=block_state["block_type"],
                )

            errors: list[str] = []
            # True once any tier fetched the page but extraction yielded nothing
            # (distinguishes EMPTY from FAILED, where every tier raised/was
            # unavailable).
            reached_without_content = False
            # Static result tagged as a JS shell: escalate to the browser tiers
            # for the hydrated page, but keep it as a last-resort fallback.
            thin_static_result: dict[str, Any] | None = None

            # --- 1. Scrapling AsyncFetcher (fast static HTTP) ---
            tier_start = time.perf_counter()
            try:
                logger.info(f"[webcrawler] Using Scrapling AsyncFetcher for: {url}")
                result = await self._run_tier_with_proxy_retry(
                    "scrapling-static",
                    lambda: self._crawl_with_async_fetcher(url, block_state),
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
                    reached_without_content = True
                    errors.append("Scrapling static: empty extraction")
                    self._log_tier_outcome(
                        "scrapling-static", url, tier_start, "empty"
                    )
            except Exception as exc:
                errors.append(f"Scrapling static: {exc!s}")
                self._log_tier_outcome(
                    "scrapling-static", url, tier_start, "error", exc
                )

            # --- 2. Scrapling DynamicFetcher (full browser) ---
            tier_start = time.perf_counter()
            try:
                logger.info(f"[webcrawler] Using Scrapling DynamicFetcher for: {url}")
                result = await self._run_tier_with_proxy_retry(
                    "scrapling-dynamic",
                    lambda: self._crawl_with_dynamic(url, block_state),
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
                reached_without_content = True
                errors.append("Scrapling dynamic: empty extraction")
                self._log_tier_outcome("scrapling-dynamic", url, tier_start, "empty")
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
            try:
                logger.info(f"[webcrawler] Using Scrapling StealthyFetcher for: {url}")
                result = await self._run_tier_with_proxy_retry(
                    "scrapling-stealthy",
                    lambda: self._crawl_with_stealthy(url, captcha_state, block_state),
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
                reached_without_content = True
                errors.append("Scrapling stealthy: empty extraction")
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

    async def _run_tier_with_proxy_retry(
        self,
        tier: str,
        attempt: Callable[[], Awaitable[dict[str, Any] | None]],
    ) -> dict[str, Any] | None:
        """Run one fetch tier, retrying once on a proxy error when pool-backed.

        ``03b`` rotation: a pool-backed ``CustomProxyProvider`` yields the *next*
        endpoint on every ``get_proxy_url()`` call, so simply re-invoking the tier
        rotates the proxy. Bounded to a single extra attempt per tier — no
        unbounded fan-out on billable crawls. Single-endpoint providers
        (including the server-side-rotating ``dataimpulse``) skip the retry
        entirely (``is_pool_backed()`` is ``False``), since retrying the same
        static endpoint would just re-hit the same dead proxy. Non-proxy errors
        (and ``NotImplementedError`` from the browser tiers) propagate unchanged
        for the caller's existing per-tier handling.
        """
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
        self, url: str, block_state: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's AsyncFetcher (static HTTP) + Trafilatura.

        AsyncFetcher is httpx/curl_cffi based and does not launch a browser
        subprocess, making it safe to call from any asyncio event loop. Returns
        ``None`` when Trafilatura cannot extract meaningful content (e.g. JS
        rendered SPAs) so the caller can fall through to the browser tiers.
        """
        fetch_start = time.perf_counter()
        # ``impersonate="chrome"`` makes curl_cffi present a real Chrome TLS
        # ClientHello (JA3/JA4) instead of its default fingerprint, keeping the
        # static tier coherent with the browser tiers' UA (see 03e §2b).
        page = await AsyncFetcher.get(
            url,
            stealthy_headers=True,
            impersonate="chrome",
            proxy=get_proxy_url(),
            timeout=20,
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

        status = getattr(page, "status", None)
        if status is not None and status >= 400:
            # 03e: classify here too — this early return skips _build_result, and
            # the static tier is the first/cheapest hit, so the 403/429 bot-gate
            # (the most common block signal) would otherwise never be labeled.
            if block_state is not None:
                block_state["block_type"] = classify_block(
                    status, getattr(page, "html_content", None)
                )
            logger.info(
                "%s tier=scrapling-static url=%s fetch_ms=%.1f status=%s outcome=http_error",
                _PERF,
                url,
                fetch_ms,
                status,
            )
            return None

        # Trafilatura extraction is CPU-bound (100ms+ on large pages); run it
        # off-loop so concurrent requests aren't stalled. The browser tiers get
        # this for free by calling _build_result inside their worker threads.
        result = await asyncio.to_thread(
            self._build_result,
            page.html_content,
            url,
            "scrapling-static",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=status,
            block_state=block_state,
        )
        if result and looks_like_js_shell(
            len(page.html_content or ""), len(result.get("content") or "")
        ):
            # Tag rather than drop: crawl_url escalates to the browser tiers but
            # keeps this as a fallback if they all fail (e.g. no subprocess
            # support on Windows dev loops).
            result["thin_static"] = True
        return result

    async def _crawl_with_dynamic(
        self, url: str, block_state: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's DynamicFetcher (full browser) + Trafilatura.

        Runs the sync fetch in a worker thread so it works on any event loop,
        including Windows ``SelectorEventLoop`` which cannot spawn subprocesses.
        """
        return await asyncio.to_thread(self._crawl_with_dynamic_sync, url, block_state)

    def _crawl_with_dynamic_sync(
        self, url: str, block_state: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Synchronous DynamicFetcher crawl executed in a worker thread."""
        fetch_start = time.perf_counter()
        page = DynamicFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=30000,
            proxy=get_proxy_url(),
            page_action=scroll_to_bottom,
        )
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        return self._build_result(
            page.html_content,
            url,
            "scrapling-dynamic",
            allow_raw_fallback=False,
            fetch_ms=fetch_ms,
            status=getattr(page, "status", None),
            block_state=block_state,
        )

    async def _crawl_with_stealthy(
        self,
        url: str,
        captcha_state: dict[str, Any] | None = None,
        block_state: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Crawl URL using Scrapling's StealthyFetcher (patchright-Chromium) + Trafilatura.

        Last-resort tier with anti-bot features. Runs the sync fetch in a worker
        thread for the same event-loop-safety reasons as DynamicFetcher. Falls
        back to the raw HTML when Trafilatura extraction is empty.

        ``captcha_state`` (03d) is mutated in place by the captcha page_action
        (attempts/solved) so ``crawl_url`` can surface it on the outcome.
        ``block_state`` (03e) is populated by ``_build_result`` with the block
        classification of the fetched page.
        """
        return await asyncio.to_thread(
            self._crawl_with_stealthy_sync, url, captcha_state, block_state
        )

    def _crawl_with_stealthy_sync(
        self,
        url: str,
        captcha_state: dict[str, Any] | None = None,
        block_state: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Synchronous StealthyFetcher crawl executed in a worker thread."""
        fetch_start = time.perf_counter()
        # Capture the proxy endpoint ONCE so the captcha solver egresses from the
        # SAME IP as this fetch (tokens are IP-bound). Re-calling get_proxy_url()
        # inside the page_action would rotate a pool-backed provider to a
        # different IP and invalidate the token (03d proxy-coherence caveat).
        proxy = get_proxy_url()

        # Build the captcha page_action only when solving is enabled (and not
        # process-latched); auto-scroll always runs after it so lazy-loaded
        # content behind a bot wall is captured too (captcha first: scrolling a
        # challenge interstitial is pointless).
        captcha_action = None
        if captcha_state is not None and captcha_enabled():
            captcha_action = build_captcha_page_action(
                captcha_state, proxy, get_captcha_config()
            )

        def page_action(page: Any) -> Any:
            if captcha_action is not None:
                page = captcha_action(page)
            return scroll_to_bottom(page)

        # ``solve_cloudflare=True`` runs the full Turnstile/Interstitial challenge
        # loop; scoped to this last-resort tier only (it spins up the browser).
        # Scrapling runs solve_cloudflare BEFORE page_action, so Cloudflare is
        # cleared first, then our captcha injector runs.
        fetch_kwargs: dict[str, Any] = {
            "headless": True,
            "network_idle": True,
            "block_ads": True,
            "solve_cloudflare": True,
            "proxy": proxy,
        }
        # 03e Slice A: merge config-driven stealth levers (block_webrtc,
        # hide_canvas, google_search, dns_over_https, geoip locale/timezone).
        # Keys never collide with the core kwargs above; defaults preserve
        # today's behavior and add no crawl-speed regression.
        fetch_kwargs.update(build_stealthy_kwargs(get_stealth_config()))
        fetch_kwargs["page_action"] = page_action
        page = StealthyFetcher.fetch(url, **fetch_kwargs)
        fetch_ms = (time.perf_counter() - fetch_start) * 1000
        return self._build_result(
            page.html_content,
            url,
            "scrapling-stealthy",
            allow_raw_fallback=True,
            fetch_ms=fetch_ms,
            status=getattr(page, "status", None),
            block_state=block_state,
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
    ) -> dict[str, Any] | None:
        """
        Extract markdown + metadata from raw HTML using Trafilatura.

        Args:
            raw_html: Raw HTML source from a fetcher.
            url: Original URL (used as the metadata source/title fallback).
            crawler_type: Identifier of the tier that produced the HTML.
            allow_raw_fallback: When True, return the raw HTML as content if
                Trafilatura cannot extract anything (used by the last-resort
                stealthy tier). When False, return ``None`` so the caller can
                fall through to the next tier.
            fetch_ms: Time spent fetching the page (for perf logging).
            status: HTTP status code returned by the fetcher (for perf logging).

        Returns:
            Result dict (content/metadata/crawler_type) or ``None``.
        """
        # 03e: classify the fetched page (additive telemetry/routing only — never
        # gates SUCCESS). Done before the early returns so EMPTY/no-extraction
        # pages still get labeled. Last tier to fetch wins in block_state.
        if block_state is not None:
            block_state["block_type"] = classify_block(status, raw_html)

        html_len = len(raw_html) if raw_html else 0

        if not raw_html or len(raw_html.strip()) == 0:
            self._log_build(
                crawler_type, url, fetch_ms, 0.0, status, html_len, 0, "empty_html"
            )
            return None

        extract_start = time.perf_counter()
        extracted_content: str | None = None
        trafilatura_metadata = None

        try:
            extracted_content = trafilatura.extract(
                raw_html,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                include_images=True,
                include_links=True,
            )
            trafilatura_metadata = trafilatura.extract_metadata(raw_html)

            if extracted_content and len(extracted_content.strip()) == 0:
                extracted_content = None
        except Exception:
            extracted_content = None

        # Repair chain for provably lossy extraction: trafilatura sometimes
        # classifies pricing cards / stat grids as boilerplate. If the DOM shows
        # currency amounts the markdown lost, retry with favor_recall, then fall
        # back to sanitized whole-body markdown. Guarded by the currency check,
        # so ordinary pages never pay for a second extraction pass.
        if extracted_content and dropped_currency_amounts(raw_html, extracted_content):
            try:
                recall = trafilatura.extract(
                    raw_html,
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
                whole = markdown_of_whole_body(raw_html)
                if whole and _CURRENCY_AMOUNT_RE.search(whole):
                    extracted_content = whole
            logger.info(
                f"{_PERF} event=lossy_repair url={url} recovered="
                f"{bool(_CURRENCY_AMOUNT_RE.search(extracted_content))}"
            )

        extract_ms = (time.perf_counter() - extract_start) * 1000

        if not extracted_content and not allow_raw_fallback:
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

        metadata: dict[str, str] = {"source": url}
        if trafilatura_metadata:
            if trafilatura_metadata.title:
                metadata["title"] = trafilatura_metadata.title
            if trafilatura_metadata.description:
                metadata["description"] = trafilatura_metadata.description
            if trafilatura_metadata.author:
                metadata["author"] = trafilatura_metadata.author
            if trafilatura_metadata.date:
                metadata["date"] = trafilatura_metadata.date
        metadata.setdefault("title", url)

        content = extracted_content if extracted_content else raw_html
        self._log_build(
            crawler_type,
            url,
            fetch_ms,
            extract_ms,
            status,
            html_len,
            len(content),
            "extracted" if extracted_content else "raw_fallback",
        )

        # One DOM parse feeds both views: the rich per-anchor inventory (agent
        # output — anchor text is the raw material for entity extraction) and
        # the URL-only frontier for ``site_crawler.crawl_site``.
        link_records = extract_link_records(raw_html, url)
        return {
            "content": content,
            "metadata": metadata,
            "crawler_type": crawler_type,
            # Next-hop targets for ``site_crawler.crawl_site``; ignored by
            # single-URL callers.
            "links": [
                r["url"] for r in link_records if r["kind"] not in ("email", "tel")
            ],
            "link_records": link_records,
            # Lead-gen signals harvested from raw HTML (footer/legal boilerplate
            # that Trafilatura strips from ``content``). Dict form so callers can
            # pass it straight through without importing the dataclass.
            "contacts": extract_contacts(raw_html).as_dict(),
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

    def format_to_structured_document(
        self, crawl_result: dict[str, Any], exclude_metadata: bool = False
    ) -> str:
        """
        Format crawl result as a structured document.

        Args:
            crawl_result: Result from crawl_url method
            exclude_metadata: If True, excludes ALL metadata fields from the document.
                            This is useful for content hash generation to ensure the hash
                            only changes when actual content changes, not when metadata
                            (which often contains dynamic fields like timestamps, IDs, etc.) changes.

        Returns:
            Structured document string
        """
        metadata = crawl_result["metadata"]
        content = crawl_result["content"]

        document_parts = ["<DOCUMENT>"]

        # Include metadata section only if not excluded
        if not exclude_metadata:
            document_parts.append("<METADATA>")
            for key, value in metadata.items():
                document_parts.append(f"{key.upper()}: {value}")
            document_parts.append("</METADATA>")

        document_parts.extend(
            [
                "<CONTENT>",
                "FORMAT: markdown",
                "TEXT_START",
                content,
                "TEXT_END",
                "</CONTENT>",
                "</DOCUMENT>",
            ]
        )

        return "\n".join(document_parts)
