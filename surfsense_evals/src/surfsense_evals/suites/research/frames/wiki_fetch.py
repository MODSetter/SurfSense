"""Wikipedia article fetcher → plain-text markdown, with disk cache.

We hit the MediaWiki action API for *plain text* extracts:

    GET https://en.wikipedia.org/w/api.php
        ?action=query&prop=extracts&explaintext=true
        &redirects=1&titles=<Title>&format=json&formatversion=2

This avoids HTML→markdown conversion (and its many edge cases). The
``explaintext=true`` mode strips infoboxes / templates / wikilinks
and returns clean section-headered prose, which is exactly what we
want SurfSense to chunk + embed. We prepend ``# <Title>\n\n`` so the
markdown has a visible H1 (helps SurfSense's chunker preserve doc
identity at the top of the first chunk).

Caching: every fetched article lands in
``<bench_dir>/wiki/<sanitised-title>.md`` and is reused on subsequent
runs. The cache key is the URL-decoded title (e.g.
``Charlotte_Brontë`` regardless of source URL casing or
percent-encoding).

Politeness: 2 RPS rate limit + a descriptive User-Agent (Wikimedia
asks for one). We don't parallelise above 2 RPS — this is a courtesy
to Wikipedia and only ~300 articles for the n=100 sample.
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = (
    "SurfSense-Evals/0.1 (https://github.com/MODSetter/SurfSense; "
    "research-benchmark fetch; respects 2 RPS rate limit)"
)


@dataclass(frozen=True)
class WikiArticle:
    """One fetched article + metadata."""

    title: str  # canonical title returned by MW (post-redirect)
    source_url: str  # the URL we were asked to fetch
    markdown_path: Path  # where the cached body lives on disk
    n_chars: int  # length of the body (post-prepend H1)
    redirected_from: str | None = None


# ---------------------------------------------------------------------------
# Title <-> URL helpers
# ---------------------------------------------------------------------------


_WIKI_PATH_RE = re.compile(r"^/wiki/(?P<title>[^?#]+)$")


def title_from_url(url: str) -> str:
    """Pull the page title out of a wiki URL.

    ``https://en.wikipedia.org/wiki/Charlotte_Bront%C3%AB`` → ``Charlotte Brontë``.
    Spaces are preserved (the API accepts spaces and underscores
    interchangeably; we use spaces to keep cache filenames human-readable).
    """

    parsed = urllib.parse.urlparse(url)
    if parsed.netloc and "wikipedia.org" not in parsed.netloc:
        raise ValueError(f"Not a Wikipedia URL: {url!r}")
    match = _WIKI_PATH_RE.match(parsed.path)
    if not match:
        raise ValueError(f"Unrecognised wiki path: {parsed.path!r}")
    raw_title = urllib.parse.unquote(match.group("title"))
    # MW treats underscores and spaces as equivalent; spaces are friendlier.
    return raw_title.replace("_", " ").strip()


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._\- ]")


def cache_filename_for_title(title: str) -> str:
    """Map a title to a filesystem-safe filename.

    Replaces every non-(alnum / ``._- `` / space) character with ``_``.
    Title collisions are rare (FRAMES only has English Wikipedia titles)
    and a final ``hash(title)[:8]`` would obscure the otherwise-readable
    filenames; we accept the (vanishingly small) collision risk.
    """

    safe = _FILENAME_SAFE.sub("_", title)
    safe = safe.strip().replace(" ", "_")
    return f"{safe}.md"


# ---------------------------------------------------------------------------
# Async fetcher with rate limiting + retry
# ---------------------------------------------------------------------------


class WikiFetcher:
    """Polite fetch + disk cache + redirect handling."""

    def __init__(
        self,
        *,
        cache_dir: Path,
        rate_limit_rps: float = 2.0,
        timeout_s: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._min_interval = 1.0 / max(rate_limit_rps, 0.1)
        self._last_request_at = 0.0
        self._rate_lock = asyncio.Lock()
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)
        self._max_retries = max_retries

    async def _throttle(self) -> None:
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            wait = self._last_request_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = asyncio.get_event_loop().time()

    async def fetch(
        self,
        url: str,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> WikiArticle | None:
        """Fetch one article. Returns ``None`` only if MW reports the title is missing.

        Raises on transport errors after retries. Caller decides
        whether to abort the whole ingest or continue with the
        successfully-fetched subset.
        """

        try:
            title = title_from_url(url)
        except ValueError as exc:
            logger.warning("Skipping non-wiki URL %s: %s", url, exc)
            return None

        cache_path = self._cache_dir / cache_filename_for_title(title)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return WikiArticle(
                title=title,
                source_url=url,
                markdown_path=cache_path,
                n_chars=cache_path.stat().st_size,
            )

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                await self._throttle()
                payload = await self._fetch_extract(title, http=http)
                break
            except (httpx.HTTPError, RuntimeError) as exc:
                last_exc = exc
                wait = 1.0 * (2**attempt)
                logger.warning(
                    "wiki fetch %r attempt %d failed: %s; retry in %.1fs",
                    title,
                    attempt + 1,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)
        else:
            assert last_exc is not None
            raise last_exc

        page = payload.get("page") or {}
        if not page or page.get("missing"):
            logger.warning("Wikipedia reports missing page for %r (url=%s)", title, url)
            return None

        canonical_title = str(page.get("title") or title).strip()
        body = str(page.get("extract") or "").strip()
        if not body:
            logger.warning("Wikipedia returned empty extract for %r", title)
            return None
        markdown = f"# {canonical_title}\n\n{body}\n"
        cache_path.write_text(markdown, encoding="utf-8")
        return WikiArticle(
            title=canonical_title,
            source_url=url,
            markdown_path=cache_path,
            n_chars=len(markdown),
            redirected_from=title if canonical_title != title else None,
        )

    async def _fetch_extract(
        self,
        title: str,
        *,
        http: httpx.AsyncClient | None,
    ) -> dict:
        """One MW API call. Returns ``{'page': {...}}`` (formatversion=2)."""

        params = {
            "action": "query",
            "prop": "extracts",
            "explaintext": "true",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
            "titles": title,
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if http is not None:
            response = await http.get(
                WIKI_API, params=params, headers=headers, timeout=self._timeout
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    WIKI_API, params=params, headers=headers, timeout=self._timeout
                )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"MediaWiki API error: {data['error']!r}")
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            return {"page": {}}
        return {"page": pages[0]}


__all__ = [
    "WIKI_API",
    "USER_AGENT",
    "WikiArticle",
    "WikiFetcher",
    "cache_filename_for_title",
    "title_from_url",
]
