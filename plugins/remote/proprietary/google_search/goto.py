"""Resolve Google's opaque ``/goto`` result redirects back to real URLs.

Google rolled out ``/goto?url=<blob>`` server-side redirects on the desktop
SERP in Jul 2026 (confirmed by Google, ~full rollout since), replacing the
destination ``href`` on every outbound result link. The blob is a base64url
protobuf — ``uint32`` version + bytes — whose payload is **encrypted with a key
only Google holds**, so unlike the older ``/url?q=<target>`` form it cannot be
decoded offline no matter how much of it we parse. Following the 302 is the
only way back to the destination, which is what this module does.

One resolution is a bodyless GET that reads the ``Location`` header (~300 B).
A page's links are resolved as one **wave on one keep-alive session**, so ten
links cost about one CONNECT+TLS plus a few multiplexed round trips (1.3 s for
10 links, against 2.2-3.6 s for one-off requests). A link still unanswered
after :data:`_HEDGE_AFTER_S` is also tried on a fresh exit, and the first
answer wins, so one slow exit no longer sets the page's tail (17 s seen).
The render reports its links as soon as they attach (:class:`GotoPrefetch`),
so most waves finish while the page is still expanding.

Requests egress through the **rotating** gateway, not the sticky IP that
rendered the page. The redirect carries no session state (it resolves with no
Google cookies at all — verified), so a wave's few gateway connections spread
this load across the vendor pool instead of concentrating it on a warm, solved
IP we would rather not get re-walled.

``ponytail:`` best-effort by design — a link that will not resolve keeps its
``/goto`` URL rather than being dropped, so a resolver outage degrades the
``url`` field on some results instead of losing the results themselves. The
ceiling is one request per outbound link; if Google ever rate-limits ``/goto``
hard enough that this stops scaling, the upgrade path is a shared
(Redis-backed) blob→destination cache, since the same result URL recurs across
queries and pages.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable, Iterator

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged

from .captcha import is_sorry_url
from .fetch import CONSENT_COOKIES
from .parsers import GOTO_PREFIX
from .schemas import SerpItem

logger = logging.getLogger(__name__)

_PLUGIN = "google-search"
# A redirect is one small round trip; anything slower is a bad exit IP, and
# waiting on it just delays the page for a field we degrade gracefully on.
# (connect incl. the proxy CONNECT and TLS, read): curl caps the whole request
# at their sum and makes one attempt.
_TIMEOUT = (4.0, 6.0)
# Attempts per link, each on a fresh exit: the hedged first try on the wave's
# session (plus its hedge), then one more on a new gateway connection.
_ATTEMPTS = 2
# Requests in flight per wave on its one session. A link's hedge timer starts
# only once it has a stream, so a link merely queued is never hedged.
_STREAMS = 8
# A kept-connection /goto answers in 0.1-0.4 s and a fresh one in about 1 s;
# past this the exit is the slow one, so the link is also sent on a fresh exit.
_HEDGE_AFTER_S = float(os.getenv("GOOGLE_SEARCH_GOTO_HEDGE_S", "1.5"))
# AI Overview / AI Mode sources add 6-15 links per page. They ride the same
# waves as the organic links, mostly during the render; 0 rewrites them only
# when another carrier shares their link, and otherwise keeps their working
# google.com redirect.
_RESOLVE_AI_SOURCES = os.getenv("GOOGLE_SEARCH_GOTO_AI_SOURCES", "1") == "1"
# Resolve the links while the page renders (0: only after the parse, as before).
PREFETCH = os.getenv("GOOGLE_SEARCH_GOTO_PREFETCH", "1") != "0"
# Send a wave over one keep-alive session, one exit IP (0: each link one-off on
# a fresh exit, the request shape before the waves).
_WAVE_SESSION = os.getenv("GOOGLE_SEARCH_GOTO_WAVE_SESSION", "1") != "0"


def _blocked(response: http.RawResponse) -> bool:
    """A refusal: a block status, or a redirect to Google's /sorry wall.

    The Location of an answer is the result's own site, which may have a /sorry
    page of its own, so only Google's host and path count.
    """
    location = response.location()
    return (
        http.default_blocked(response)
        or is_sorry_url(response.url)
        or (bool(location) and is_sorry_url(location, base=response.url))
    )


def _answered(response: http.RawResponse) -> bool:
    return bool(response.location()) and not response.blocked


async def _get(
    link: str, h: sessions.SessionHolder | None, *, attempt: int
) -> http.RawResponse:
    """One bodyless GET of ``link``: on the wave's session, or one-off on a new
    gateway connection (a new exit IP) when ``h`` is None."""
    kw = {
        "cookies": CONSENT_COOKIES,
        "timeout": _TIMEOUT,
        "allow_redirects": False,
        "attempt": attempt,
        "is_blocked": _blocked,
    }
    if h is not None:
        seen = h.rotations
        response = await h.request("GET", link, stage="goto", **kw)
        if response.blocked:
            # The rest of the wave would hit the refusing exit too.
            await h.rotate("blocked", seen=seen)
        return response
    return await http.request(
        "GET",
        link,
        plugin=_PLUGIN,
        stage="goto",
        proxy=sessions.Exit().proxy_url(),
        **kw,
    )


async def _resolve_one(
    link: str, h: sessions.SessionHolder | None, gate: asyncio.Semaphore
) -> str | None:
    """Follow one ``/goto`` redirect one hop; return its ``Location``."""
    async with gate:
        for attempt in range(_ATTEMPTS):
            try:
                if attempt == 0:
                    response = await hedged(
                        lambda i: _get(link, h if i == 0 else None, attempt=0),
                        after_s=_HEDGE_AFTER_S,
                        accept=_answered,
                        plugin=_PLUGIN,
                        stage="goto",
                    )
                else:  # refused or failed: a new gateway connection, a new IP
                    response = await _get(link, None, attempt=attempt)
            except http.TransportError as e:
                logger.debug("[google_search][goto] attempt %d error: %s", attempt, e)
                continue
            if _answered(response):
                return response.location()
            logger.debug(
                "[google_search][goto] attempt %d: status=%s, no Location",
                attempt,
                response.status,
            )
    return None


async def resolve_links(links: Iterable[str]) -> dict[str, str | None]:
    """Resolve ``links`` as one wave on one gateway session.

    Returns link -> destination, None for a link that would not resolve.
    """
    unique = list(dict.fromkeys(links))
    if not unique:
        return {}
    gate = asyncio.Semaphore(_STREAMS)
    if not _WAVE_SESSION:
        destinations = await asyncio.gather(
            *(_resolve_one(link, None, gate) for link in unique)
        )
        return dict(zip(unique, destinations, strict=True))
    async with sessions.holder(_PLUGIN, max_streams=_STREAMS) as h:
        destinations = await asyncio.gather(
            *(_resolve_one(link, h, gate) for link in unique)
        )
    return dict(zip(unique, destinations, strict=True))


class GotoPrefetch:
    """Resolves a render's ``/goto`` links on the request loop while it renders.

    Made on the request loop. The render calls :meth:`feed` from the browser
    loop once the organic results attach and again after the expansion; each
    feed's new links start a wave. :meth:`discard` drops what a render that is
    not returned (walled, failed) fed; :meth:`close` cancels what still runs
    and drops any feed that lands after it.
    """

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._seen: set[str] = set()
        self._waves: list[asyncio.Future[dict[str, str | None]]] = []
        self._render = 0  # bumped by discard(): an older render's feeds are dropped
        self._closed = False

    def feed(self, hrefs: Iterable[str]) -> None:
        """Thread-safe: schedule ``/goto?...`` hrefs for resolution."""
        links = [GOTO_PREFIX + href.split("?", 1)[1] for href in hrefs if "?" in href]
        if links:
            self._loop.call_soon_threadsafe(self._start, links, self._render)

    def _start(self, links: list[str], render: int) -> None:
        # A feed queued as the call ended would start a wave nobody awaits.
        if self._closed or render != self._render:
            return
        fresh = [link for link in links if link not in self._seen]
        if fresh:
            self._seen.update(fresh)
            self._waves.append(asyncio.ensure_future(resolve_links(fresh)))

    def discard(self) -> None:
        """Forget the current render's links (request loop only)."""
        self._render += 1
        self._seen.clear()
        self._cancel()
        self._waves.clear()

    async def results(self) -> dict[str, str | None]:
        """Every fed link -> its destination (None if unresolved), once the
        waves are done. A link absent here was never fed."""
        await asyncio.sleep(0)  # start feeds queued just before the render returned
        resolved: dict[str, str | None] = {}
        for outcome in await asyncio.gather(*self._waves, return_exceptions=True):
            if isinstance(outcome, dict):
                resolved.update(outcome)
        return resolved

    def close(self) -> None:
        """Cancel the waves still running and ignore later feeds (the page
        ended or failed)."""
        self._closed = True
        self._cancel()

    def _cancel(self) -> None:
        for wave in self._waves:
            wave.cancel()


def _url_carriers(item: SerpItem, *, ai_sources: bool = True) -> Iterator:
    """Every parsed object on ``item`` whose ``url`` may be a ``/goto`` link.

    Related/suggested queries are deliberately excluded: those point back into
    Google's own ``/search`` and are meant to stay that way.
    """
    for result in (*item.organicResults, *item.paidResults):
        yield result
        yield from result.siteLinks
    yield from item.paidProducts
    yield from item.peopleAlsoAsk
    if not ai_sources:
        return
    for answer in (item.aiOverview, item.aiModeResult):
        if answer is not None:
            yield from answer.sources


async def resolve_item_urls(
    item: SerpItem, prefetch: GotoPrefetch | None = None
) -> int:
    """Rewrite every ``/goto`` URL on ``item`` in place; return how many resolved.

    Deduplicates first: a SERP repeats the same destination across a result and
    its "jump to text" sibling, and an AI Overview usually cites pages that are
    also organic results, so the unique-link count runs well under the raw one.
    Links the render already fed to ``prefetch`` are taken from it, resolved or
    not (a link that failed there had its attempts); only the rest are fetched.
    """
    carriers = [c for c in _url_carriers(item) if (c.url or "").startswith(GOTO_PREFIX)]
    fetched = _url_carriers(item, ai_sources=_RESOLVE_AI_SOURCES)
    links = list({c.url for c in fetched if (c.url or "").startswith(GOTO_PREFIX)})
    if not links:
        return 0
    known = await prefetch.results() if prefetch is not None else {}
    left = [link for link in links if link not in known]
    if left:
        known.update(await resolve_links(left))
    resolved = {link: known[link] for link in links if known.get(link)}
    for carrier in carriers:
        destination = resolved.get(carrier.url)
        if destination:
            carrier.url = destination
    if len(resolved) < len(links):
        logger.warning(
            "[google_search][goto] resolved %d/%d links; the rest keep their "
            "redirect URL",
            len(resolved),
            len(links),
        )
    logger.info(
        "[google_search][perf] goto links=%d prefetched=%d after_parse=%d resolved=%d",
        len(links),
        len(links) - len(left),
        len(left),
        len(resolved),
    )
    return len(resolved)
