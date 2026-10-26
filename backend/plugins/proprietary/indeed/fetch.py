"""Browser fetch seam for the Indeed scraper, on the shared browser pool.

Indeed fronts its origin with Cloudflare plus an anonymous-bot check that bounces
some sessions to ``secure.indeed.com/auth``. Pages come from one kept browser
context per Indeed country (``browser_pool.page(kept="indeed:<cc>")``) on a sticky
exit pinned to that country, so its Cloudflare clearance and cookies carry across
calls instead of being solved again by a new Chromium every call.

A navigation waits for DOMContentLoaded only (job cards and the viewjob model are
server-rendered) and runs the Cloudflare solver only when the page is a challenge.
Job details come from Indeed's own ``spa=1`` JSON, fetched from inside the page
the way its job pane does, a few at once. A blocked page burns the context, which
quarantines its exit, and the next attempt builds a new one on a new exit. All
egress is through the residential proxy.

Kill switches, read at import: ``INDEED_KEPT_CONTEXT=0`` gives every page a fresh
context and exit; ``INDEED_SPA_DETAILS=0`` loads each job's page instead of its
``spa=1`` JSON; ``INDEED_WARM_FIRST=1`` lands on the home page before every target,
and ``INDEED_ALWAYS_SOLVE=1`` runs the Cloudflare solver after every navigation,
as the old recipe did; ``INDEED_PIN_COUNTRY=0`` leases exits in any country (the
kept context stays per Indeed country).
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

from proprietary.scraping import browser_pool, sessions, settle
from proprietary.scraping.browser_pool import LaunchProfile
from proprietary.scraping.logged_host import logged_host

from .parsers import extract_initial_data, spa_model
from .url_resolver import domain_country

logger = logging.getLogger(__name__)


class IndeedAccessBlockedError(RuntimeError):
    """Every rotated IP was bounced to Indeed's security wall."""


class _WalledError(Exception):
    """This exit was walled; leaving the page block with it burns the context."""


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value not in ("0", "false", "no", "off")


_KEPT = _flag("INDEED_KEPT_CONTEXT", True)
_SPA = _flag("INDEED_SPA_DETAILS", True)
_WARM_FIRST = _flag("INDEED_WARM_FIRST", False)
_ALWAYS_SOLVE = _flag("INDEED_ALWAYS_SOLVE", False)
_PIN_COUNTRY = _flag("INDEED_PIN_COUNTRY", True)

# Per attempt (navigation plus any solve); the largest successful solve took 32 s.
_PAGE_TIMEOUT_S = 40.0
_SOLVE_TIMEOUT_S = 35.0
# The home-page warm-up is only a fallback for an auth-wall bounce.
_WARM_TIMEOUT_S = 15.0
# A dead exit fails at the commit; DOMContentLoaded then gets the page timeout.
_COMMIT_TIMEOUT_MS = 12_000
_PAGE_TIMEOUT_MS = 20_000
# Details are best-effort: they may not hold the call longer than this.
_DETAILS_TIMEOUT_S = 30.0
_MAX_ROTATIONS = 3
# spa=1 requests in flight at once from one kept context (so one exit), as
# Indeed's own pane would send; the context's pages take turns.
_SPA_BATCH = 5
_SPA_TIMEOUT_MS = 15_000
# spa=1 answers 401 once Indeed flags the exit; two in one page retire it.
_SPA_UNAUTHORIZED_BURN = 2
_GOOGLE = "https://www.google.com/"
_PROFILE = LaunchProfile(block_webrtc=True)

# Markers of a Cloudflare / security-check interstitial served instead of jobs.
_BLOCK_MARKERS = (
    "secure.indeed.com",
    "bot-detection",
    "security check",
    "challenge-platform",
    "just a moment",
    "verify you are human",
    "hcaptcha",
)

# Each answer is [status, body]; a network error or timeout is status 0.
_SPA_JS = """async ([urls, ms]) => Promise.all(urls.map(async (u) => {
  try {
    const r = await fetch(u, {credentials: 'include',
      headers: {accept: 'application/json'}, signal: AbortSignal.timeout(ms)});
    return [r.status, r.status === 200 ? await r.text() : ''];
  } catch (e) { return [0, String(e)]; }
}))"""

# The calling tool's progress reporter (server.py sets it per call), so a call
# that rotates or solves a challenge is not a silent stream.
on_stage: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "indeed_on_stage", default=None
)


async def _stage(message: str) -> None:
    report = on_stage.get()
    if report is not None:
        await report(message)


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape used by scraper output."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _looks_blocked(html: str, final_url: str, status: Any = None) -> bool:
    """Whether a response is an interstitial rather than a real page.

    A 403/429 counts whatever the body says: an IP-level block page carries none
    of the markers, and parsing it silently gave zero jobs.
    """
    if not html or status in (403, 429):
        return True
    haystack = (final_url + " " + html[:6000]).lower()
    return any(marker in haystack for marker in _BLOCK_MARKERS)


def _bounced(final_url: str) -> bool:
    """Whether Indeed sent the page to its sign-in wall."""
    return (urlsplit(final_url).hostname or "").lower() == "secure.indeed.com"


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


@dataclass
class Fetched:
    """A page's HTML and the viewjob models of the jobs asked for, by job key."""

    html: str
    details: dict[str, dict[str, Any]] = field(default_factory=dict)


# Country -> a page on that country's context; tests pass a fake.
PageOpener = Callable[[str], AbstractAsyncContextManager[Any]]
Runner = Callable[[Callable[[], Awaitable[Any]]], Awaitable[Any]]


def _pool_page(country: str) -> AbstractAsyncContextManager[Any]:
    """A page on the kept context for ``country``, on a sticky exit in it.

    The pool calls the lease only when it builds a context, so a warm call takes
    no new exit; it gives the lease back, quarantined if burned, on close.
    """
    return browser_pool.page(
        "indeed",
        _PROFILE,
        kept=f"indeed:{country}" if _KEPT else None,
        proxy=lambda: sessions.lease_exit("in", country if _PIN_COUNTRY else None),
        timeout_ms=_PAGE_TIMEOUT_MS,
    )


async def _goto(
    p: Any, url: str, *, referer: str | None = _GOOGLE
) -> tuple[str, int | None]:
    """Navigate to DOMContentLoaded; solve Cloudflare only when it challenged.

    Returns the HTML and the landing status (``None`` once a challenge was
    solved, since the status was the challenge's).
    """
    land = await settle.goto(
        p.page, url, referer=referer, commit_timeout_ms=_COMMIT_TIMEOUT_MS
    )
    html = await settle.page_content(p.page)
    kind = settle.challenge_kind(land.status, land.headers, html)
    if kind is None and not _ALWAYS_SOLVE:
        return html, land.status
    if kind is None:
        # The kill switch: the solver looks for a challenge itself, as the old
        # recipe's did on every page.
        kind = "managed"
    else:
        await _stage(f"solving a Cloudflare {kind} challenge")
    if not await settle.solve_challenge(p, kind, timeout_s=_SOLVE_TIMEOUT_S):
        p.burn(f"cloudflare {kind}")
        raise _WalledError(f"cloudflare {kind} challenge unsolved")
    return await settle.page_content(p.page), None


async def _warm(p: Any, url: str) -> None:
    """Land on the domain home with a Google referer, capped; a failure only logs."""
    try:
        async with asyncio.timeout(_WARM_TIMEOUT_S):
            await _goto(p, _origin(url) + "/")
    except _WalledError:
        raise
    except Exception as e:
        logger.info("[indeed] warm-up failed on %s: %r", _origin(url), e)


# Kept contexts that have landed a real page (Cloudflare cleared, if it asked).
# Until one has, its pages land one at a time: concurrent targets on a new context
# each met their own challenge (live m2 cold: two solves of 21 and 23 s at once).
_cleared: weakref.WeakSet[Any] = weakref.WeakSet()
_failed: weakref.WeakSet[Any] = weakref.WeakSet()
_first_landing: weakref.WeakKeyDictionary[Any, asyncio.Lock] = (
    weakref.WeakKeyDictionary()
)
# One spa=1 batch in flight per kept context, whichever of its pages sends it.
_spa_turn: weakref.WeakKeyDictionary[Any, asyncio.Lock] = weakref.WeakKeyDictionary()


@asynccontextmanager
async def _landing_turn(p: Any) -> AsyncIterator[None]:
    """Wait for this page's turn to land on a context no page has landed on yet.

    One page at a time lands on a new context, so one solve clears it for all; a
    page whose turn comes after a walled one gives up, so its attempt moves to a
    new context. Entered outside the attempt's timeout: the wait is not its fault.
    """
    context = p.context
    if context not in _cleared:
        turn = _first_landing.setdefault(context, asyncio.Lock())
        if turn.locked():
            # Up to a page timeout per page ahead: not a silent one.
            await _stage("waiting for the page ahead to clear Cloudflare")
        async with turn:
            if context in _failed:
                raise _WalledError("the page ahead on this context was walled")
            if context not in _cleared:
                try:
                    yield
                except Exception:  # not a cancel: the next page may try
                    _failed.add(context)
                    raise
                _cleared.add(context)
                return
    yield


async def _land(p: Any, url: str) -> str:
    """Navigate ``p`` to ``url`` and return its HTML once it is a real page.

    A bounce to the sign-in wall warms the home page once and retries there;
    any other wall burns the context and raises :class:`_WalledError`.
    """
    if _WARM_FIRST:
        await _warm(p, url)
    html, status = await _goto(p, url)
    if _bounced(p.page.url):
        logger.info(
            "[indeed] bounced to the sign-in wall on %s; warming", logged_host(url)
        )
        await _warm(p, url)
        html, status = await _goto(p, url)
    if _looks_blocked(html, p.page.url, status):
        p.burn("security wall")
        raise _WalledError(f"walled (status {status}) at {_origin(p.page.url)}")
    return html


async def _spa_models(
    p: Any, wanted: Mapping[str, str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Fetch ``spa=1`` answers from inside the page, a batch at a time.

    Returns the models by job key and the keys that got none. The batch that
    brings two 401s burns the context and is the last: the rest are not asked.
    """
    models: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    unauthorized = 0
    keys = list(wanted)
    turn = _spa_turn.setdefault(p.context, asyncio.Lock())
    for start in range(0, len(keys), _SPA_BATCH):
        batch = keys[start : start + _SPA_BATCH]
        async with turn:
            answers = await p.page.evaluate(
                _SPA_JS, [[wanted[k] for k in batch], _SPA_TIMEOUT_MS]
            )
        for job_key, (status, body) in zip(batch, answers, strict=True):
            model = spa_model(body) if status == 200 else None
            if model is not None:
                models[job_key] = model
                continue
            failed.append(job_key)
            unauthorized += status == 401
            logger.info("[indeed] spa detail answered %s", status)
        if unauthorized >= _SPA_UNAUTHORIZED_BURN:
            # Indeed flagged this exit: send nothing more on it, and the next
            # call moves to a new one.
            p.burn("spa 401")
            failed.extend(keys[start + _SPA_BATCH :])
            break
    return models, failed


async def _details(p: Any, wanted: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """Viewjob models for ``wanted`` (job key -> page-relative ``spa=1`` URL).

    Best-effort and bounded: a job whose ``spa=1`` answer fails is loaded as a
    page instead, unless the answers burned the exit; a wall or timeout leaves
    the rest without details rather than failing the page they came from.
    """
    models: dict[str, dict[str, Any]] = {}
    pending = list(wanted)
    try:
        async with asyncio.timeout(_DETAILS_TIMEOUT_S):
            if _SPA:
                found, pending = await _spa_models(p, wanted)
                models.update(found)
                if p.burned:
                    return models
            base = _origin(p.page.url)
            for job_key in pending:
                html = await _land(p, urljoin(base, f"/viewjob?jk={job_key}"))
                model = extract_initial_data(html)
                if model is not None:
                    models[job_key] = model
    except Exception as e:  # a wall, a timeout or a page error on one job
        logger.warning("[indeed] detail fetch failed: %r", e)
    return models


class IndeedSession:
    """One call's access to Indeed: pages and job details, rotating on blocks.

    Holds no browser itself: every attempt borrows a page from the pool's kept
    context for the target's country, so concurrent targets share its clearance.
    """

    def __init__(
        self,
        open_page: PageOpener = _pool_page,
        runner: Runner = browser_pool.run,
    ) -> None:
        self._open = open_page
        self._run = runner
        self.rotations = 0

    async def fetch_page(
        self,
        url: str,
        *,
        details_for: Callable[[str], Mapping[str, str]] | None = None,
        max_rotations: int | None = None,
    ) -> Fetched:
        """A search or company page, and the details ``details_for(html)`` asks for.

        ``details_for`` maps the page HTML to ``{job key: spa=1 URL}``; it runs on
        the browser loop, so it must be pure. ``max_rotations=0`` fails fast on a
        page no fresh IP will clear.
        """

        async def attempt(p: Any) -> Fetched:
            async with _landing_turn(p), asyncio.timeout(_PAGE_TIMEOUT_S):
                html = await _land(p, url)
            wanted = details_for(html) if details_for is not None else {}
            if not wanted:
                return Fetched(html)
            await _stage(f"fetching {len(wanted)} job details")
            return Fetched(html, await _details(p, wanted))

        return await self._with_rotation(url, attempt, max_rotations)

    async def fetch_job(self, url: str, job_key: str) -> dict[str, Any] | None:
        """A single job's viewjob model, or ``None`` when its page has none.

        On a cleared context, lands on the site's robots.txt (a same-origin page
        that costs nothing to render; no referer, as a typed address has none),
        asks ``spa=1`` for the job, and loads the job page only when that fails. A new context has no Cloudflare clearance,
        so spa=1 would get a 403: it loads the job page at once.
        """

        async def attempt(p: Any) -> dict[str, Any] | None:
            if _SPA and p.context in _cleared:
                async with asyncio.timeout(_PAGE_TIMEOUT_S):
                    _, status = await _goto(
                        p, _origin(url) + "/robots.txt", referer=None
                    )
                    if status in (403, 429):
                        p.burn(f"status {status}")
                        raise _WalledError(f"status {status} on robots.txt")
                    models, _ = await _spa_models(
                        p, {job_key: f"/viewjob?jk={job_key}&spa=1"}
                    )
                if job_key in models:
                    return models[job_key]
            async with _landing_turn(p), asyncio.timeout(_PAGE_TIMEOUT_S):
                return extract_initial_data(await _land(p, url))

        return await self._with_rotation(url, attempt, None)

    async def _with_rotation(
        self,
        url: str,
        attempt: Callable[[Any], Awaitable[Any]],
        max_rotations: int | None,
    ) -> Any:
        """Run ``attempt`` on a pooled page; on a wall or failure, retry on a new exit.

        The failed attempt's exception leaves the page block, which burns its kept
        context, so the next attempt's page is on a new context and exit.
        """
        budget = _MAX_ROTATIONS if max_rotations is None else max_rotations
        country = domain_country(urlsplit(url).hostname)
        tries = 0
        while True:
            await _stage(f"fetching {url}" + (f" (try {tries + 1})" if tries else ""))

            async def on_loop() -> Any:
                async with self._open(country) as p:
                    return await attempt(p)

            try:
                result = await self._run(on_loop)
            except _WalledError as e:
                logger.info("[indeed] blocked on %s: %s", logged_host(url), e)
            except TimeoutError:
                logger.warning("[indeed] fetch timed out on %s", logged_host(url))
            except Exception as e:
                logger.warning("[indeed] fetch failed on %s: %r", logged_host(url), e)
            else:
                await _stage(f"fetched {url}")
                return result

            if tries >= budget:
                raise IndeedAccessBlockedError(
                    f"Indeed refused {url} after {tries + 1} attempt(s)"
                )
            tries += 1
            self.rotations += 1
            logger.info("[indeed] rotated session (rotation #%d)", self.rotations)


@asynccontextmanager
async def open_session() -> AsyncIterator[IndeedSession]:
    """An :class:`IndeedSession` for one call; the pool owns the browser."""
    yield IndeedSession()
