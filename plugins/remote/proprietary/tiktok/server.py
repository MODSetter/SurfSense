"""SurfSense's TikTok plugin: public videos, profiles, comments and accounts, behind the license."""

from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.license_check.license_access import LicenseAccess
from proprietary.tiktok import (
    TikTokAccessBlockedError,
    TikTokScrapeInput,
    scrape_tiktok,
    scrape_tiktok_comments,
    scrape_tiktok_trending,
    search_tiktok_users,
)

# Bound one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100
# Characters of a caption or comment the summary shows; the whole is in the result.
SUMMARY_TEXT = 100

access = LicenseAccess()


def server() -> MCPServer:
    tiktok = MCPServer("tiktok")

    @tiktok.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "TikTok URLs to scrape: a video, a profile (/@<user>), a hashtag "
                    "(/tag/<name>), or a search URL. Provide these OR profiles/"
                    "hashtags (at least one source is required)."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        profiles: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description="Profile usernames (with or without a leading '@').",
            ),
        ] = [],  # noqa: B006
        hashtags: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description="Hashtag names to scrape, without the leading '#'.",
            ),
        ] = [],  # noqa: B006
        results_per_page: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max videos to pull per profile/hashtag target.",
            ),
        ] = 10,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max total items to return across all sources.",
            ),
        ] = 10,
    ) -> CallToolResult:
        """Scrape public TikTok videos. Use urls, profiles, or hashtags. To find accounts by keyword, use user_search."""
        if not any((urls, profiles, hashtags)):
            raise ToolError(
                "Provide at least one of 'urls', 'profiles', or 'hashtags'."
            )
        urls = _http_urls(urls)

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        request = TikTokScrapeInput(
            startUrls=[{"url": url} for url in urls],
            profiles=profiles,
            hashtags=hashtags,
            resultsPerPage=results_per_page,
        )
        try:
            items = await scrape_tiktok(request, limit=max_items, on_item=heard)
        except TikTokAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"TikTok refused anonymous access: {error}") from error
        return _result(f"{len(items)} TikTok items", items)

    @tiktok.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def comments(
        ctx: Context,
        video_urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_SOURCES,
                description=(
                    "TikTok video URLs (/@<user>/video/<id>) to pull comments from."
                ),
            ),
        ],
        comments_per_video: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Max comments to return per video."),
        ] = 20,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max total comments to return across all videos.",
            ),
        ] = 20,
    ) -> CallToolResult:
        """Scrape the public comments of TikTok videos: text, author, likes, and reply counts."""
        video_urls = _http_urls(video_urls)

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        items = await scrape_tiktok_comments(
            video_urls,
            per_video=comments_per_video,
            limit=max_items,
            on_item=heard,
        )
        return _result(f"{len(items)} TikTok comments", items)

    @tiktok.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def trending(
        ctx: Context,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max trending videos to return from the Explore feed.",
            ),
        ] = 20,
    ) -> CallToolResult:
        """Get the current trending TikTok videos from the Explore feed."""

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        items = await scrape_tiktok_trending(count=max_items, on_item=heard)
        return _result(f"{len(items)} trending TikTok videos", items)

    @tiktok.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def user_search(
        ctx: Context,
        queries: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_SOURCES,
                description=(
                    "Keywords to search for TikTok accounts (e.g. names, brands)."
                ),
            ),
        ],
        results_per_query: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Max accounts to return per query."),
        ] = 10,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max total accounts to return across all queries.",
            ),
        ] = 10,
    ) -> CallToolResult:
        """Find public TikTok accounts by keyword: name, followers, bio, and verification."""

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        items = await search_tiktok_users(
            queries, per_query=results_per_query, limit=max_items, on_item=heard
        )
        return _result(f"{len(items)} TikTok accounts", items)

    return tiktok


def _http_urls(urls: list[str]) -> list[str]:
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


def _result(heading: str, items: list[dict[str, Any]]) -> CallToolResult:
    """What the agent reads first; the items themselves are in the structured result."""
    lines = [heading, *(_line(item) for item in items)]
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
        structured_content={"items": items},
    )


def _line(item: dict[str, Any]) -> str:
    """One item of any kind the scraper emits: video, account, comment or error."""
    if item.get("errorCode"):
        where = item.get("input") or item.get("url") or ""
        return f"- [{item['errorCode']}] {where}: {item.get('error') or ''}"
    if "webVideoUrl" in item:
        author = (item.get("authorMeta") or {}).get("name") or ""
        text = (item.get("text") or "")[:SUMMARY_TEXT]
        return (
            f"- @{author}: {text} ({item.get('playCount') or 0} plays) "
            f"{item.get('webVideoUrl') or ''}"
        )
    if "videoWebUrl" in item:
        kind = "reply" if item.get("repliesToId") else "comment"
        text = (item.get("text") or "")[:SUMMARY_TEXT]
        return f"- [{kind}] {item.get('uniqueId') or ''}: {text}"
    return (
        f"- [account] @{item.get('name') or ''} ({item.get('nickName') or ''}), "
        f"{item.get('fans') or 0} followers {item.get('profileUrl') or ''}"
    )
