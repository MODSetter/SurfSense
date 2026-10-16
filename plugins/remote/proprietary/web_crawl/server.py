"""SurfSense's Web Crawl plugin: pages read as clean markdown, or a site crawled by its links, behind the license."""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import MAX_TEXT_BYTES, tool_result, wants_text_only
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle
from proprietary.web_crawl.connector import (
    DEFAULT_MAX_LINKS,
    PageLimits,
    WebCrawlerConnector,
)
from proprietary.web_crawl.items import crawl_item
from proprietary.web_crawl.site_crawler import crawl_site
from proprietary.web_crawl.url_policy import canonical_url

# The backend capability's caps: they bound one synchronous call's fan-out.
MAX_START_URLS = 20
MAX_CRAWL_DEPTH = 5
MAX_CRAWL_PAGES = 200
MAX_URL_PATTERNS = 25
MAX_LINKS = 2000
# Each page's share of the text the agent reads is the cap split between the
# pages, less its other fields as written, but never under this many bytes.
_MIN_TEXT_SHARE = 300
# Room for the summary line and the newlines between the pages.
_HEAD_ROOM = 200
# What the markdown field adds to a page's line besides its text.
_MARKDOWN_KEY_BYTES = len(',"markdown":""')
# Contacts and links an agent reads per page; the structured result has them all.
_AGENT_CONTACTS = 10
_AGENT_LINKS = 30

access = shared_access()

logger = logging.getLogger(__name__)

# What the warm-up extracts: a date, an author and non-English text wake
# trafilatura's and htmldate's lazily built tables before the first call.
_WARM_UP_PAGE = (
    "<html><head><title>Warm-up</title>"
    '<meta name="author" content="Ada Lovelace">'
    '<meta property="article:published_time" content="2024-05-01"></head>'
    "<body><article><h1>Warm-up</h1><p>"
    + "Le pain se fait avec de la farine, de l'eau et du sel. " * 8
    + '</p><a href="/about">About</a> contact@example.com</article></body></html>'
)


# A page this short sends trafilatura to its justext rescue, whose stoplists
# (110 ms) are built on first use.
_WARM_UP_SHORT_PAGE = (
    "<html><head><title>Short</title></head><body><h1>Short</h1>"
    "<p>This page is for use in examples.</p></body></html>"
)


def _warm_extractors() -> None:
    engine = WebCrawlerConnector()
    for page in (_WARM_UP_PAGE, _WARM_UP_SHORT_PAGE):
        engine._build_result(
            page, "https://example.com/", "warm-up", allow_raw_fallback=False
        )


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Holds the shared pools open and warms the extractors (CPU only, no proxy)."""
    async with lifecycle.lifespan():
        try:
            await asyncio.to_thread(_warm_extractors)
        except Exception:
            # A failed warm-up must not end the lifespan: the pools would not close.
            logger.warning("[web-crawl] warm-up failed", exc_info=True)
        yield


def server() -> MCPServer:
    web_crawl = MCPServer("web-crawl")
    engine = WebCrawlerConnector()

    @web_crawl.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def crawl(
        ctx: Context,
        start_urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_START_URLS,
                description=(
                    "http(s) pages to read. With max_crawl_depth 0 only these are "
                    "fetched; deeper, they are where the crawl starts."
                ),
            ),
        ],
        max_crawl_depth: Annotated[
            int,
            Field(
                ge=0,
                le=MAX_CRAWL_DEPTH,
                description=(
                    "Link hops to follow from each start URL: 0 reads only the start "
                    "URLs, 1 also the pages they link to. Stays on the start URL's site."
                ),
            ),
        ] = 0,
        max_crawl_pages: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_CRAWL_PAGES,
                description="Most pages fetched in all, start URLs included.",
            ),
        ] = 10,
        max_length: Annotated[
            int,
            Field(ge=1, description="Most characters of markdown kept per page."),
        ] = 50_000,
        max_links: Annotated[
            int,
            Field(
                ge=0,
                le=MAX_LINKS,
                description=(
                    "Most links kept per page: the site's own pages first, then "
                    "profile, email and phone links. linksTotal counts them all."
                ),
            ),
        ] = DEFAULT_MAX_LINKS,
        include_url_patterns: Annotated[
            list[str] | None,
            Field(
                max_length=MAX_URL_PATTERNS,
                description=(
                    "Regexes a discovered link must match to be followed; empty "
                    "follows every same-site link. Start URLs are always read."
                ),
            ),
        ] = None,
        exclude_url_patterns: Annotated[
            list[str] | None,
            Field(
                max_length=MAX_URL_PATTERNS,
                description="Regexes that stop a discovered link being followed; beat includes.",
            ),
        ] = None,
    ) -> CallToolResult:
        """Read web pages as clean markdown text, or crawl a site by following its links.

        Each page comes back with its title, text, links with their anchor text,
        and the emails, phones and social profiles it shows.
        """
        _refuse_non_http(start_urls)
        _refuse_bad_patterns(
            [*(include_url_patterns or []), *(exclude_url_patterns or [])]
        )
        # The crawl reads a start URL given twice once.
        seeds = len({canonical_url(url.strip()) for url in start_urls})
        total = min(seeds, max_crawl_pages) if max_crawl_depth == 0 else max_crawl_pages

        await stage(ctx, "reading pages", total=total)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {total} pages read", done=count, total=total)

        async def moved(message: str) -> None:
            await stage(ctx, message)

        pages = await crawl_site(
            engine,
            [url.strip() for url in start_urls],
            max_crawl_depth=max_crawl_depth,
            max_crawl_pages=max_crawl_pages,
            include_patterns=include_url_patterns,
            exclude_patterns=exclude_url_patterns,
            on_item=heard,
            on_stage=moved,
            limits=PageLimits(max_length=max_length, max_links=max_links),
        )
        items = [crawl_item(page, max_length, max_links) for page in pages]
        if not any(item["status"] == "success" for item in items):
            raise ToolError(
                "No page could be read. "
                + " ".join(item["error"] or item["url"] for item in items)
            )
        return tool_result(
            _summary(items),
            items,
            project=_projection(len(items)),
            # Page text is cut by its share of the byte cap, not at 2,000 chars.
            clip_chars=MAX_TEXT_BYTES,
            text_only=wants_text_only(ctx),
        )

    return web_crawl


def _refuse_non_http(urls: list[str]) -> None:
    refused = [
        url
        for url in urls
        if urlsplit(url.strip()).scheme not in ("http", "https")
        or not urlsplit(url.strip()).netloc
    ]
    if refused:
        raise ToolError(f"Only http(s) pages can be read: {', '.join(refused)}")


def _refuse_bad_patterns(patterns: list[str]) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"{pattern} is not a regex: {exc}") from exc


def _summary(items: list[dict[str, Any]]) -> str:
    """The header line: pages read and how they ended; the pages follow it."""
    read = sum(item["status"] == "success" for item in items)
    missed = len(items) - read
    noun = "page" if len(items) == 1 else "pages"
    return f"{len(items)} {noun}: {read} read" + (f", {missed} not" if missed else "")


def _clip_bytes(text: str | None, limit: int) -> str | None:
    """``text`` cut to ``limit`` UTF-8 bytes, never mid-character."""
    if text is None or len(text) * 4 <= limit:
        return text
    cut = text.encode("utf-8")[:limit].decode("utf-8", "ignore")
    return cut if cut == text else cut + "…"


def _without_empties(value: Any) -> Any:
    """``value`` as ``tool_result`` writes it: nulls and empty values dropped."""
    if isinstance(value, dict):
        kept = {key: _without_empties(inner) for key, inner in value.items()}
        return {key: inner for key, inner in kept.items() if not _empty(inner)}
    if isinstance(value, list):
        return [inner for inner in map(_without_empties, value) if not _empty(inner)]
    return value


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str | list | dict) and not value)


def _json_bytes(value: Any) -> int:
    """Bytes ``value`` takes in the reply's text."""
    line = json.dumps(
        _without_empties(value),
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return len(line.encode())


def _clip_escaped(text: str | None, limit: int) -> str | None:
    """``text`` cut so it takes at most ``limit`` bytes once escaped in JSON.

    Newlines and quotes take two bytes each there, so a byte cut alone overruns.
    """
    if text is None:
        return None
    room = limit
    while room > 0:
        cut = _clip_bytes(text, room)
        over = _json_bytes(cut) - 2 - limit
        if over <= 0:
            return cut
        room -= over
    return _clip_bytes(text, 0)


def _projection(count: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """What an agent reads of each of ``count`` pages: every page gets its share."""
    line_room = (MAX_TEXT_BYTES - _HEAD_ROOM) // count

    def project(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") or {}
        loaded = item["crawl"]["loadedUrl"]
        contacts = item.get("contacts") or {}
        links = (item.get("links") or []) if count == 1 else []
        markdown = item.get("markdown")
        wanted = min(_MIN_TEXT_SHARE, _json_bytes(markdown) - 2) if markdown else 0
        kept = _AGENT_CONTACTS
        while True:
            fields = {
                "url": item["url"],
                "loadedUrl": loaded if loaded != item["url"] else None,
                "status": item["status"],
                "error": item.get("error"),
                "title": metadata.get("title"),
                "description": metadata.get("description"),
                "author": metadata.get("author"),
                "date": metadata.get("date"),
                "depth": item["crawl"]["depth"] or None,
                "markdown": None,
                "contacts": {kind: values[:kept] for kind, values in contacts.items()},
                "links": [
                    {"text": link.get("text"), "url": link.get("url")}
                    for link in links[:_AGENT_LINKS]
                ],
                "linksTotal": item.get("linksTotal"),
            }
            room = line_room - _json_bytes(fields) - _MARKDOWN_KEY_BYTES
            if room >= wanted or kept <= 1:
                break
            # A team page's contacts would crowd out its text, and an
            # overfull reply drops whole pages: fewer contacts each.
            kept //= 2
        fields["markdown"] = _clip_escaped(markdown, max(_MIN_TEXT_SHARE, room))
        return fields

    return project
