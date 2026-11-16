"""SurfSense's TikTok plugin: public videos, profiles, comments and accounts, behind the license."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle
from proprietary.tiktok import (
    TikTokAccessBlockedError,
    TikTokScrapeInput,
    on_stage,
    scrape_tiktok,
    scrape_tiktok_comments,
    scrape_tiktok_trending,
    search_tiktok_users,
    warm_browser,
)

# Bound one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100
# Hashtags and mentions of a video an agent reads before it needs the full item.
_TAGS_SHOWN = 10

logger = logging.getLogger(__name__)

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Launches the headless browser in the background: about 0.5 s on a desktop
    and 5 s in prod off the first browser call. It opens no page, so it spends no
    proxy credit; TIKTOK_WARM_BROWSER=0 skips it."""
    async with lifecycle.lifespan():
        warming = None
        if os.getenv("TIKTOK_WARM_BROWSER", "1") != "0":
            warming = asyncio.create_task(_warm())
        try:
            yield
        finally:
            if warming is not None:
                warming.cancel()


async def _warm() -> None:
    try:
        await warm_browser()
    except Exception:
        # The first browser call launches it instead.
        logger.warning("[tiktok] browser warm-up failed", exc_info=True)


async def _staged[T](ctx: Context, run: Callable[[], Awaitable[T]]) -> T:
    """Run ``run`` with the scraper's stage reports routed to the tool's progress."""
    token = on_stage.set(lambda message: stage(ctx, message))
    try:
        return await run()
    finally:
        on_stage.reset(token)


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
        """Scrape public TikTok videos. Use urls, profiles, or hashtags. Each profile also returns its account (name, followers, bio) as the first item, and it counts toward max_items. To find accounts by keyword, use user_search."""
        if not any((urls, profiles, hashtags)):
            raise ToolError(
                "Provide at least one of 'urls', 'profiles', or 'hashtags'."
            )
        urls = _http_urls(urls)
        await stage(ctx, "scraping TikTok", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} items", done=count, total=max_items
            )

        request = TikTokScrapeInput(
            startUrls=[{"url": url} for url in urls],
            profiles=profiles,
            hashtags=hashtags,
            resultsPerPage=results_per_page,
        )
        try:
            items = await _staged(
                ctx, lambda: scrape_tiktok(request, limit=max_items, on_item=heard)
            )
        except TikTokAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"TikTok refused anonymous access: {error}") from error
        return _result(ctx, "TikTok items", items)

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
        await stage(ctx, "fetching comments", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} comments", done=count, total=max_items
            )

        items = await _staged(
            ctx,
            lambda: scrape_tiktok_comments(
                video_urls,
                per_video=comments_per_video,
                limit=max_items,
                on_item=heard,
            ),
        )
        return _result(ctx, "TikTok comments", items, _comments_projection(items))

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
        await stage(ctx, "fetching the Explore feed", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} videos", done=count, total=max_items
            )

        items = await _staged(
            ctx, lambda: scrape_tiktok_trending(count=max_items, on_item=heard)
        )
        return _result(ctx, "trending TikTok videos", items)

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
        await stage(ctx, "searching accounts", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} accounts", done=count, total=max_items
            )

        items = await _staged(
            ctx,
            lambda: search_tiktok_users(
                queries, per_query=results_per_query, limit=max_items, on_item=heard
            ),
        )
        return _result(ctx, "TikTok accounts", items)

    return tiktok


def _http_urls(urls: list[str]) -> list[str]:
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


def _result(
    ctx: Context,
    noun: str,
    items: list[dict[str, Any]],
    project: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> CallToolResult:
    """A header line, then each item's fields an agent answers from, one per line.

    ``noun`` is the plural; a count of one drops its trailing "s".
    """
    errors = sum(1 for item in items if item.get("errorCode"))
    found = len(items) - errors
    heading = f"{found} {noun.removesuffix('s') if found == 1 else noun}"
    if errors:
        heading += f", {errors} error{'' if errors == 1 else 's'}"
    return tool_result(
        heading, items, project=project or _projected, text_only=wants_text_only(ctx)
    )


def _comments_projection(
    items: list[dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Name each comment's video only when the comments span more than one.

    The URL is about 85 bytes a line, a quarter of the text cap at 100 comments.
    """
    videos = {item.get("videoWebUrl") for item in items if "videoWebUrl" in item}
    if len(videos) > 1:
        return _projected

    def one_video(item: dict[str, Any]) -> dict[str, Any]:
        projected = _projected(item)
        projected.pop("video", None)
        return projected

    return one_video


def _projected(item: dict[str, Any]) -> dict[str, Any]:
    """One item of any kind the scraper emits: video, account, comment or error."""
    if item.get("errorCode"):
        return {
            "errorCode": item["errorCode"],
            "error": item.get("error"),
            "input": item.get("input") or item.get("url"),
        }
    if "webVideoUrl" in item:
        author = item.get("authorMeta") or {}
        video = item.get("videoMeta") or {}
        music = item.get("musicMeta") or {}
        return {
            "url": item.get("webVideoUrl"),
            "author": author.get("name"),
            "authorVerified": author.get("verified"),
            "text": item.get("text"),
            "language": item.get("textLanguage"),
            "created": item.get("createTimeISO"),
            "plays": item.get("playCount"),
            "likes": item.get("diggCount"),
            "comments": item.get("commentCount"),
            "shares": item.get("shareCount"),
            "saves": item.get("collectCount"),
            "durationSeconds": video.get("duration"),
            "music": music.get("musicName"),
            "hashtags": [
                tag.get("name") for tag in (item.get("hashtags") or [])[:_TAGS_SHOWN]
            ],
            "mentions": (item.get("mentions") or [])[:_TAGS_SHOWN],
            "isAd": item.get("isAd") or None,
            "isPinned": item.get("isPinned") or None,
            "isSlideshow": item.get("isSlideshow") or None,
        }
    if "videoWebUrl" in item:
        return {
            "author": item.get("uniqueId"),
            "text": item.get("text"),
            "likes": item.get("diggCount"),
            "replies": item.get("replyCommentTotal"),
            "created": item.get("createTimeISO"),
            "repliesToId": item.get("repliesToId"),
            "id": item.get("id"),
            "video": item.get("videoWebUrl"),
        }
    return {
        "account": item.get("name"),
        "name": item.get("nickName"),
        "url": item.get("profileUrl"),
        "verified": item.get("verified"),
        "followers": item.get("fans"),
        "following": item.get("following"),
        "likes": item.get("heart"),
        "videos": item.get("video"),
        "private": item.get("privateAccount"),
        "bio": item.get("signature"),
    }
