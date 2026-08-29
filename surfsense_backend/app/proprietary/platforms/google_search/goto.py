"""Resolve Google's opaque ``/goto`` result redirects back to real URLs.

Google rolled out ``/goto?url=<blob>`` server-side redirects on the desktop
SERP in Jul 2026 (confirmed by Google, ~full rollout since), replacing the
destination ``href`` on every outbound result link. The blob is a base64url
protobuf — ``uint32`` version + bytes — whose payload is **encrypted with a key
only Google holds**, so unlike the older ``/url?q=<target>`` form it cannot be
decoded offline no matter how much of it we parse. Following the 302 is the
only way back to the destination, which is what this module does.

One resolution is a bodyless GET that reads the ``Location`` header (~300 B).
Links are resolved **concurrently**, so a full SERP page (~10 links) costs
about one round trip rather than ten: ~2 s through the residential proxy,
against a ~12-16 s warm render, so it does not move the per-page budget much.

Requests egress through the **rotating** gateway, not the sticky IP that
rendered the page. The redirect carries no session state (it resolves with no
Google cookies at all — verified), so a fresh exit IP per link spreads this
load across the vendor pool instead of concentrating it on a warm, solved IP
we would rather not get re-walled.

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
from collections.abc import Iterator

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

from .fetch import CONSENT_COOKIES
from .parsers import GOTO_PREFIX
from .schemas import SerpItem

logger = logging.getLogger(__name__)

# A redirect is one small round trip; anything slower is a bad exit IP, and
# waiting on it just delays the page for a field we degrade gracefully on.
_TIMEOUT_S = float(os.getenv("GOOGLE_SEARCH_GOTO_TIMEOUT_S", "15"))
# Attempts per link. The gateway rotates its exit IP per request, so a retry is
# genuinely a different route rather than the same failing one twice.
_ATTEMPTS = 2
# Concurrent resolutions. One SERP page carries ~10 outbound links, so this
# default resolves a page in a single wave.
_CONCURRENCY = int(os.getenv("GOOGLE_SEARCH_GOTO_CONCURRENCY", "10"))


async def _resolve_one(
    url: str, proxy: str | None, gate: asyncio.Semaphore
) -> str | None:
    """Follow one ``/goto`` redirect one hop; return its ``Location``."""
    async with gate:
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = await AsyncFetcher.get(
                    url,
                    cookies=CONSENT_COOKIES,
                    proxy=proxy,
                    stealthy_headers=True,
                    timeout=_TIMEOUT_S,
                    follow_redirects=False,
                )
            except Exception as e:  # dead/slow exit IP; the retry gets a new one
                logger.debug("[google_search][goto] attempt %d error: %s", attempt, e)
                continue
            location = response.headers.get("location") or response.headers.get(
                "Location"
            )
            if location:
                return location
            logger.debug(
                "[google_search][goto] attempt %d: status=%s, no Location",
                attempt,
                response.status,
            )
    return None


def _url_carriers(item: SerpItem) -> Iterator:
    """Every parsed object on ``item`` whose ``url`` may be a ``/goto`` link.

    Related/suggested queries are deliberately excluded: those point back into
    Google's own ``/search`` and are meant to stay that way.
    """
    for result in (*item.organicResults, *item.paidResults):
        yield result
        yield from result.siteLinks
    yield from item.paidProducts
    yield from item.peopleAlsoAsk
    for answer in (item.aiOverview, item.aiModeResult):
        if answer is not None:
            yield from answer.sources


async def resolve_item_urls(item: SerpItem) -> int:
    """Rewrite every ``/goto`` URL on ``item`` in place; return how many resolved.

    Deduplicates first: a SERP repeats the same destination across a result and
    its "jump to text" sibling, and an AI Overview usually cites pages that are
    also organic results, so the unique-link count runs well under the raw one.
    """
    carriers = [c for c in _url_carriers(item) if (c.url or "").startswith(GOTO_PREFIX)]
    if not carriers:
        return 0
    links = list({c.url for c in carriers})
    gate = asyncio.Semaphore(_CONCURRENCY)
    proxy = get_proxy_url()
    destinations = await asyncio.gather(
        *(_resolve_one(link, proxy, gate) for link in links)
    )
    resolved = {
        link: dest for link, dest in zip(links, destinations, strict=True) if dest
    }
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
    return len(resolved)
