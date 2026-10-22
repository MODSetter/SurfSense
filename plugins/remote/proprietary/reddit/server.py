"""SurfSense's Reddit plugin: public posts, comments, users and communities, behind the license."""

from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.license_check.license_access import shared_access
from proprietary.reddit import fetch
from proprietary.reddit.fetch import RedditAccessBlockedError
from proprietary.reddit.schemas import RedditScrapeInput
from proprietary.reddit.scraper import scrape_reddit
from proprietary.scraping import lifecycle

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100

access = shared_access()

# What an agent reads of each item; ids, HTML and media URLs stay in the
# structured result.
_AGENT_FIELDS = (
    "dataType",
    "title",
    "communityName",
    "username",
    "url",
    "body",
    "externalUrl",
    "upVotes",
    "numberOfComments",
    "numberOfReplies",
    "numberOfMembers",
    "flair",
    "over18",
    "createdAt",
    "postId",
    "parentId",
)

Sort = Literal["relevance", "hot", "top", "new", "rising", "comments"]
Time = Literal["hour", "day", "week", "month", "year", "all"]


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Holds the shared scraping pools open while the plugin is mounted."""
    async with lifecycle.lifespan():
        yield


def server() -> MCPServer:
    reddit = MCPServer("reddit")

    @reddit.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Reddit URLs to scrape: a post, a subreddit (/r/<name>), a user "
                    "(/user/<name>), or a search URL. Give these, search_queries or "
                    "community."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Search terms to run on Reddit. Scope them to one subreddit "
                    "with community."
                ),
            ),
        ] = [],  # noqa: B006
        community: Annotated[
            str | None,
            Field(
                description=(
                    "A subreddit name without 'r/', such as 'python'. With no "
                    "search_queries, its listing is scraped."
                )
            ),
        ] = None,
        sort: Annotated[
            Sort | None,
            Field(
                description=(
                    "Result ordering. Unset, a search orders by relevance and a "
                    "subreddit's listing by newest."
                )
            ),
        ] = None,
        time_filter: Annotated[
            Time | None, Field(description="Time window for top and search results.")
        ] = None,
        include_nsfw: Annotated[
            bool, Field(description="Include posts marked NSFW.")
        ] = False,
        skip_comments: Annotated[
            bool, Field(description="Skip comment trees: faster, posts only.")
        ] = False,
        max_items: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Most items to return in all."),
        ] = 10,
        max_posts: Annotated[
            int, Field(ge=0, description="Most posts per subreddit, user or search.")
        ] = 10,
        max_comments: Annotated[
            int, Field(ge=0, description="Most comments per post; 0 for none.")
        ] = 10,
        post_date_limit: Annotated[
            str | None, Field(description="ISO date: only posts newer than this.")
        ] = None,
        comment_date_limit: Annotated[
            str | None, Field(description="ISO date: only comments newer than this.")
        ] = None,
    ) -> CallToolResult:
        """Scrape public Reddit posts, comments and communities, anonymously."""
        if not urls and not search_queries and not community:
            raise ToolError("Give at least one of urls, search_queries or community.")
        for url in urls:
            parts = urlsplit(url.strip())
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ToolError(f"Not an http(s) URL: {url}")

        await stage(ctx, "scraping Reddit", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} items", done=count, total=max_items
            )

        request = RedditScrapeInput(
            startUrls=[{"url": url.strip()} for url in urls],
            searches=search_queries,
            searchCommunityName=community,
            sort=sort,
            time=time_filter,
            includeNSFW=include_nsfw,
            skipComments=skip_comments,
            maxItems=max_items,
            maxPostCount=max_posts,
            maxComments=max_comments,
            postDateLimit=post_date_limit,
            commentDateLimit=comment_date_limit,
        )
        # Warms and fetches report too, so a slow give-up is not a silent stream.
        token = fetch.on_stage.set(lambda message: stage(ctx, message))
        try:
            items = await scrape_reddit(request, limit=max_items, on_item=heard)
        except RedditAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"Reddit refused anonymous access: {error}") from error
        finally:
            fetch.on_stage.reset(token)
        return tool_result(
            _summary(items),
            items,
            project=_projected,
            text_only=wants_text_only(ctx),
        )

    return reddit


def _summary(items: list[dict[str, Any]]) -> str:
    """The header line: how many items of each kind; the items follow it."""
    kinds = Counter(item.get("dataType") or "item" for item in items)
    counts = ", ".join(
        f"{count} {kind}{'' if count == 1 else 's'}" for kind, count in kinds.items()
    )
    return f"{len(items)} Reddit items" + (f": {counts}" if counts else "")


def _projected(item: dict[str, Any]) -> dict[str, Any]:
    return {field: item.get(field) for field in _AGENT_FIELDS}
