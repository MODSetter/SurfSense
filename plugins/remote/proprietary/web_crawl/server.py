"""SurfSense's Web Crawl plugin: pages read as clean markdown, or a site crawled by its links, behind the license."""

import re
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.license_check.license_access import LicenseAccess
from proprietary.web_crawl.connector import WebCrawlerConnector
from proprietary.web_crawl.items import crawl_item
from proprietary.web_crawl.site_crawler import crawl_site

# The backend capability's caps: they bound one synchronous call's fan-out.
MAX_START_URLS = 20
MAX_CRAWL_DEPTH = 5
MAX_CRAWL_PAGES = 200
MAX_URL_PATTERNS = 25
# A single page is usually "read this article": its text leads the summary.
SUMMARY_TEXT_CHARS = 2000

access = LicenseAccess()


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
        total = (
            min(len(start_urls), max_crawl_pages)
            if max_crawl_depth == 0
            else max_crawl_pages
        )

        async def heard(count: int) -> None:
            await ctx.report_progress(count, total)

        pages = await crawl_site(
            engine,
            [url.strip() for url in start_urls],
            max_crawl_depth=max_crawl_depth,
            max_crawl_pages=max_crawl_pages,
            include_patterns=include_url_patterns,
            exclude_patterns=exclude_url_patterns,
            on_item=heard,
        )
        items = [crawl_item(page, max_length) for page in pages]
        if not any(item["status"] == "success" for item in items):
            raise ToolError(
                "No page could be read. "
                + " ".join(item["error"] or item["url"] for item in items)
            )
        return CallToolResult(
            content=[TextContent(type="text", text=_summary(items))],
            structured_content={"items": items},
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
    """What the agent reads first; every page whole is in the structured result."""
    lines = [f"{len(items)} {'page' if len(items) == 1 else 'pages'} read"]
    for item in items:
        if item["status"] == "success":
            title = (item["metadata"] or {}).get("title") or item["url"]
            lines.append(f"  {title} {item['url']}")
        else:
            lines.append(f"  {item['url']}: {item['status']}, {item['error']}")
    if len(items) == 1:
        text = items[0]["markdown"] or ""
        lines.extend(["", text[:SUMMARY_TEXT_CHARS]])
        if len(text) > SUMMARY_TEXT_CHARS:
            lines.append("[...the rest is in the structured result]")
    return "\n".join(lines)
