"""GET TikTok page HTML through a cookie-warmed, sticky-IP proxy session.

The warm-up mints TikTok's anonymous device cookie (``ttwid``) on the first
homepage hit; the target page then server-renders its rehydration blob. Rotates
the residential IP and re-warms on 403, backs off on 429, and raises
:class:`TikTokAccessBlockedError` only when every rotated IP refuses access.
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import suppress
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

from .errors import TikTokAccessBlockedError
from .proxy import _REQUEST_TIMEOUT_S, _current_session, proxy_session

logger = logging.getLogger(__name__)

# 403 => IP blocked; rotate and re-warm. 429 => rate limited; back off same IP.
_ROTATE_STATUS = 403
_BACKOFF_STATUS = 429
# Each rotation walks to the next country pool (see session/proxy.py). The bare
# worldwide pool never mints ``ttwid`` (proven live 2026-07-17), so warming
# relies on reaching a good country pool — budget enough rotations to try every
# one at least once (>= len(rotation FALLBACK_COUNTRIES)). Rotating is cheap
# (reopen one keep-alive connection + a 1-request warm), so spend liberally.
_MAX_ROTATIONS = 8
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

_HOME_URL = "https://www.tiktok.com/"
_TTWID_COOKIE = "ttwid"
_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}


def _response_cookie_names(page: Any) -> set[str]:
    cookies = getattr(page, "cookies", None)
    return set(cookies.keys()) if isinstance(cookies, dict) else set()


def _page_html(page: Any) -> str | None:
    for attr in ("text", "body"):
        val = getattr(page, attr, None)
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        if isinstance(val, str) and val.strip():
            return val
    return None


async def warm_session(session: Any) -> bool:
    """Mint an anonymous ``ttwid`` cookie; ``True`` if the session can now fetch."""
    with suppress(Exception):
        page = await session.get(_HOME_URL, headers=_HEADERS)
        if _TTWID_COOKIE in _response_cookie_names(page):
            return True
    return False


async def _get_page(session: Any, url: str) -> Any:
    if session is not None:
        return await session.get(url, headers=_HEADERS)
    return await AsyncFetcher.get(
        url,
        headers=_HEADERS,
        proxy=get_proxy_url(),
        stealthy_headers=True,
        timeout=_REQUEST_TIMEOUT_S,
    )


async def fetch_html(url: str) -> str | None:
    """Return page HTML, or ``None`` on 404 / non-block failure."""
    holder = _current_session.get()
    if holder is None:
        async with proxy_session():
            return await fetch_html(url)

    attempt = 0
    backoffs = 0
    while True:
        session = holder.session
        try:
            if session is not None and not holder.warmed:
                warmed_ok = await warm_session(session)
                holder.warmed = True
                if not warmed_ok:
                    if attempt < _MAX_ROTATIONS:
                        attempt += 1
                        await holder.rotate()
                        continue
                    raise TikTokAccessBlockedError(
                        f"could not warm session after {attempt} IP rotations: {url}"
                    )

            await holder.pace()
            page = await _get_page(session, url)
            status = page.status

            if status == 200:
                return _page_html(page)
            if status == 404:
                return None
            if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
                backoffs += 1
                delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
                logger.warning("[tiktok] 429 on %s; backing off %.1fs", url, delay)
                await asyncio.sleep(delay + random.uniform(0, 1))
                continue
            if status == _ROTATE_STATUS and attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            if status == _ROTATE_STATUS:
                raise TikTokAccessBlockedError(
                    f"TikTok refused {url} on {attempt} rotated IPs (403)"
                )
            logger.warning("[tiktok] GET %s returned %s", url, status)
            return None
        except TikTokAccessBlockedError:
            raise
        except Exception as e:
            logger.warning("[tiktok] GET %s failed: %s", url, e)
            if attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            return None
