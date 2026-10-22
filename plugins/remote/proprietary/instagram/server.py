"""SurfSense's Instagram plugin: public posts, reels and profiles, behind the license."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.instagram.fetch import (
    InstagramAccessBlockedError,
    InstagramLoginRequiredError,
)
from proprietary.instagram.schemas import InstagramScrapeInput
from proprietary.instagram.scraper import scrape_instagram
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100

access = shared_access()

SearchType = Literal["profile", "user"]

SEARCH_TYPE_DESCRIPTION = (
    "Discovery kind (profile-only; hashtag/place are login-walled)."
)

# Said with a login-wall refusal: what an anonymous caller can still get.
STILL_WORKS = (
    "Instagram asked for a login here, and SurfSense reads Instagram "
    "anonymously, so retrying will not help. Single post and reel URLs "
    "(instagram.com/p/<code>/ or instagram.com/reel/<code>/) still work: pass "
    "those to scrape in urls."
)


# What an agent reads of each post and profile; ids, image and video URLs and
# raw tagged-user records stay in the structured result.
_POST_FIELDS = (
    "type",
    "url",
    "caption",
    "ownerUsername",
    "timestamp",
    "likesCount",
    "commentsCount",
    "videoViewCount",
    "videoPlayCount",
    "videoDuration",
    "hashtags",
    "mentions",
    "isPinned",
    "paidPartnership",
    "productType",
    "locationName",
)
_PROFILE_FIELDS = (
    "username",
    "fullName",
    "url",
    "biography",
    "externalUrl",
    "followersCount",
    "followsCount",
    "postsCount",
    "verified",
    "private",
    "isBusinessAccount",
    "businessCategoryName",
)
_ERROR_FIELDS = ("inputUrl", "error", "errorDescription")


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Holds the shared scraping pools open while the plugin is mounted."""
    async with lifecycle.lifespan():
        yield


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
            Field(
                ge=1,
                description=(
                    "Max results per URL or per discovered target. A profile shows "
                    "a logged-out visitor its latest 12 posts or 12 reels, no more."
                ),
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
        """Scrape public Instagram posts or reels from profile/post/reel URLs, or discover public profiles via search queries.

        A profile's posts feed gives its newest posts without a video URL; for a
        video's file, scrape that post's URL (instagram.com/p/<code>/), which reads
        its own page. Its signed URL expires within hours to days, so fetch it
        when it is needed.
        """
        _one_source(urls, search_queries)

        await stage(ctx, "scraping Instagram", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} items", done=count, total=max_items
            )

        request = InstagramScrapeInput(
            resultsType=result_type,
            directUrls=urls,
            search=",".join(search_queries),
            searchType=search_type,
            resultsLimit=max_per_target,
            onlyPostsNewerThan=newer_than,
            skipPinnedPosts=skip_pinned_posts,
        )
        try:
            items = await scrape_instagram(request, limit=max_items, on_item=heard)
        except InstagramLoginRequiredError as error:
            raise ToolError(f"{error}. {STILL_WORKS}") from error
        except InstagramAccessBlockedError as error:
            # Anonymous only: a hard block cannot be retried with credentials.
            raise ToolError(
                "Instagram requires a login for this request and SurfSense scrapes "
                f"anonymously. Details: {error}"
            ) from error
        return tool_result(
            _summary(items, "posts"),
            items,
            project=_projected_post,
            text_only=wants_text_only(ctx),
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

        await stage(ctx, "scraping Instagram", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} items", done=count, total=max_items
            )

        request = InstagramScrapeInput(
            resultsType="details",
            directUrls=urls,
            search=",".join(search_queries),
            searchType=search_type,
            searchLimit=search_limit,
        )
        try:
            items = await scrape_instagram(request, limit=max_items, on_item=heard)
        except InstagramLoginRequiredError as error:
            raise ToolError(f"{error}. {STILL_WORKS}") from error
        except InstagramAccessBlockedError as error:
            raise ToolError(f"Instagram refused anonymous access: {error}") from error
        return tool_result(
            _summary(items, "profiles"),
            items,
            project=_projected_profile,
            text_only=wants_text_only(ctx),
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


def _summary(items: list[dict[str, Any]], kind: str) -> str:
    """The header line: counts only; the items follow it."""
    errors = sum(1 for item in items if item.get("error"))
    return f"{len(items)} Instagram {kind}" + (f", {errors} errors" if errors else "")


def _pick(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item.get(field) for field in fields}


def _projected_post(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("error"):
        return _pick(item, _ERROR_FIELDS)
    return _pick(item, _POST_FIELDS)


def _projected_profile(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("error"):
        return _pick(item, _ERROR_FIELDS)
    related = [
        profile.get("username")
        for profile in item.get("relatedProfiles") or []
        if isinstance(profile, dict)
    ]
    latest = [
        _projected_post(post)
        for post in item.get("latestPosts") or []
        if isinstance(post, dict)
    ]
    return {
        **_pick(item, _PROFILE_FIELDS),
        "relatedProfiles": related,
        "latestPosts": latest,
    }
