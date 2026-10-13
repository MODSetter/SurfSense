"""SurfSense's YouTube plugin: public videos, channels, playlists and comments, behind the license."""

from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.license_check.license_access import LicenseAccess
from proprietary.youtube.comments import scrape_comments
from proprietary.youtube.schemas import YouTubeCommentsInput, YouTubeScrapeInput
from proprietary.youtube.scraper import scrape_youtube

# Bound one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000
MAX_COMMENT_VIDEOS = 20
MAX_COMMENTS = 100_000

access = LicenseAccess()

CommentOrder = Literal["TOP_COMMENTS", "NEWEST_FIRST"]


def server() -> MCPServer:
    youtube = MCPServer("youtube")

    @youtube.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "YouTube URLs to scrape: video, channel (/@handle or "
                    "/channel/UC...), playlist (?list=...), shorts, or hashtag pages. "
                    "Give these or search_queries."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Search terms to run on YouTube; each returns up to max_results "
                    "videos. Give these or urls."
                ),
            ),
        ] = [],  # noqa: B006
        max_results: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_RESULTS,
                description=(
                    "Most items per source and per content type: a channel's "
                    "videos, shorts and streams are capped independently."
                ),
            ),
        ] = 10,
        download_subtitles: Annotated[
            bool,
            Field(description="Also fetch each video's subtitle track: slower."),
        ] = False,
        subtitles_language: Annotated[
            str,
            Field(
                description=(
                    "Subtitle language code, such as 'en' or 'fr'. Used when "
                    "download_subtitles is true."
                )
            ),
        ] = "en",
    ) -> CallToolResult:
        """Scrape public YouTube videos, channels, playlists, and subtitles."""
        if not urls and not search_queries:
            raise ToolError("Give at least one of urls or search_queries.")
        urls = _http_urls(urls)

        async def heard(count: int) -> None:
            await ctx.report_progress(count)

        # A channel emits three content types; each takes the caller's cap.
        request = YouTubeScrapeInput(
            startUrls=[{"url": url} for url in urls],
            searchQueries=search_queries,
            maxResults=max_results,
            maxResultsShorts=max_results,
            maxResultStreams=max_results,
            downloadSubtitles=download_subtitles,
            subtitlesLanguage=subtitles_language,
        )
        items = await scrape_youtube(request, on_item=heard)
        return CallToolResult(
            content=[TextContent(type="text", text=_videos(items))],
            structured_content={"items": items},
        )

    @youtube.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def comments(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_COMMENT_VIDEOS,
                description="YouTube video URLs to fetch comments and replies for.",
            ),
        ],
        max_comments: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_COMMENTS,
                description="Most items per video, counting comments and replies.",
            ),
        ] = 20,
        sort_by: Annotated[
            CommentOrder,
            Field(description="Most-liked first, or most-recent first."),
        ] = "NEWEST_FIRST",
    ) -> CallToolResult:
        """Fetch public YouTube comments and replies with authors, text, likes, and timestamps."""
        urls = _http_urls(urls)
        most = len(urls) * max_comments

        async def heard(count: int) -> None:
            await ctx.report_progress(count, most)

        request = YouTubeCommentsInput(
            startUrls=[{"url": url} for url in urls],
            maxComments=max_comments,
            sortCommentsBy=sort_by,
        )
        items = await scrape_comments(request, on_item=heard)
        return CallToolResult(
            content=[TextContent(type="text", text=_comments(items))],
            structured_content={"items": items},
        )

    return youtube


def _http_urls(urls: list[str]) -> list[str]:
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


def _videos(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; the items themselves are in the structured result."""
    lines = [f"{len(items)} YouTube items"]
    for item in items:
        lines.append(
            f"- [{item.get('type')}] {item.get('title') or ''} "
            f"({item.get('channelName') or ''}) {item.get('url') or ''}"
        )
    return "\n".join(lines)


def _comments(items: list[dict[str, Any]]) -> str:
    lines = [f"{len(items)} YouTube comments"]
    for item in items:
        kind = "reply" if item.get("replyToCid") else "comment"
        text = (item.get("comment") or "")[:120]
        lines.append(f"- [{kind}] {item.get('author') or ''}: {text}")
    return "\n".join(lines)
