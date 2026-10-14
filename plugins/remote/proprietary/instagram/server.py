"""SurfSense's Instagram plugin: public posts, reels and profiles, behind the license."""

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.instagram.fetch import InstagramAccessBlockedError
from proprietary.instagram.schemas import InstagramScrapeInput
from proprietary.instagram.scraper import scrape_instagram
from proprietary.license_check.license_access import LicenseAccess

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100

access = LicenseAccess()

SearchType = Literal["profile", "user"]

SEARCH_TYPE_DESCRIPTION = (
    "Discovery kind (profile-only; hashtag/place are login-walled)."
)


def server() -> MCPServer:
    instagram = MCPServer("instagram")

    @instagram.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Instagram URLs or bare profile IDs: profile, post (/p/), or "
                    "reel (/reel/). Hashtag/place URLs are unsupported "
                    "(login-walled). Provide these OR search_queries (never both)."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Discovery keywords resolved to profiles via Google (IG's "
                    "keyword search is login-walled). Provide these OR urls "
                    "(never both)."
                ),
            ),
        ] = [],  # noqa: B006
        search_type: Annotated[
            SearchType, Field(description=SEARCH_TYPE_DESCRIPTION)
        ] = "profile",
        result_type: Annotated[
            Literal["posts", "reels"],
            Field(description="Which feed to return: 'posts' or 'reels'."),
        ] = "posts",
        newer_than: Annotated[
            str | None,
            Field(
                description=(
                    "Only return posts newer than this: YYYY-MM-DD, ISO timestamp, "
                    "or relative ('1 day', '2 months'); UTC."
                )
            ),
        ] = None,
        skip_pinned_posts: Annotated[
            bool, Field(description="Exclude pinned posts (posts mode).")
        ] = False,
        max_per_target: Annotated[
            int,
            Field(ge=1, description="Max results per URL or per discovered target."),
        ] = 10,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS,
                description="Max total items to return across all sources.",
            ),
        ] = 10,
        add_parent_data: Annotated[
            bool, Field(description="Attach a dataSource block to each feed item.")
        ] = False,
    ) -> CallToolResult:
        """Scrape public Instagram posts or reels from profile/post/reel URLs, or discover public profiles via search queries."""
        _one_source(urls, search_queries)

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        request = InstagramScrapeInput(
            resultsType=result_type,
            directUrls=urls,
            search=",".join(search_queries),
            searchType=search_type,
            resultsLimit=max_per_target,
            onlyPostsNewerThan=newer_than,
            skipPinnedPosts=skip_pinned_posts,
            addParentData=add_parent_data,
        )
        try:
            items = await scrape_instagram(request, limit=max_items, on_item=heard)
        except InstagramAccessBlockedError as error:
            # Anonymous only: a hard block cannot be retried with credentials.
            raise ToolError(
                "Instagram requires a login for this request and SurfSense scrapes "
                "anonymously. Provide a profile URL or handle via urls; "
                "keyword/hashtag search needs an account and is unavailable. "
                f"Details: {error}"
            ) from error
        return CallToolResult(
            content=[TextContent(type="text", text=_posts_summary(items))],
            structured_content={"items": items},
        )

    @instagram.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def details(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Profile URLs or bare profile IDs. Provide these OR search_queries."
                ),
            ),
        ] = [],  # noqa: B006
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Discovery keywords resolved to profiles. Provide these OR urls."
                ),
            ),
        ] = [],  # noqa: B006
        search_type: Annotated[
            SearchType, Field(description=SEARCH_TYPE_DESCRIPTION)
        ] = "profile",
        search_limit: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Max discovered entities per query."),
        ] = 10,
        max_items: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Max total detail items to return."),
        ] = 10,
    ) -> CallToolResult:
        """Get public Instagram profile details: bio, follower and post counts, latest posts."""
        _one_source(urls, search_queries)

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        request = InstagramScrapeInput(
            resultsType="details",
            directUrls=urls,
            search=",".join(search_queries),
            searchType=search_type,
            searchLimit=search_limit,
        )
        try:
            items = await scrape_instagram(request, limit=max_items, on_item=heard)
        except InstagramAccessBlockedError as error:
            raise ToolError(f"Instagram refused anonymous access: {error}") from error
        return CallToolResult(
            content=[TextContent(type="text", text=_profiles_summary(items))],
            structured_content={"items": items},
        )

    return instagram


def _one_source(urls: list[str], search_queries: list[str]) -> None:
    """URLs override searches in the scraper, so naming both would drop the searches."""
    if not urls and not search_queries:
        raise ToolError("Provide at least one of 'urls' or 'search_queries'.")
    if urls and search_queries:
        raise ToolError(
            "Provide 'urls' OR 'search_queries', not both (they cannot be combined)."
        )


def _posts_summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; the items themselves are in the structured result."""
    lines = [f"{len(items)} Instagram posts"]
    for item in items:
        caption = " ".join((item.get("caption") or "").split())[:120]
        lines.append(
            f"- [{item.get('type')}] {caption} (@{item.get('ownerUsername') or ''}) "
            f"{item.get('url') or ''}"
        )
    return "\n".join(lines)


def _profiles_summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; each profile whole is in the structured result."""
    lines = [f"{len(items)} Instagram profiles"]
    for item in items:
        followers = item.get("followersCount")
        counts = f", {followers} followers" if followers is not None else ""
        lines.append(
            f"- @{item.get('username')} {item.get('fullName') or ''}{counts} "
            f"{item.get('url') or ''}"
        )
    return "\n".join(lines)
