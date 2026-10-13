"""SurfSense's Reddit plugin: public posts, comments, users and communities, behind the license."""

from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.license_check.license_access import LicenseAccess
from proprietary.reddit.fetch import RedditAccessBlockedError
from proprietary.reddit.schemas import RedditScrapeInput
from proprietary.reddit.scraper import scrape_reddit

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100

access = LicenseAccess()

Sort = Literal["relevance", "hot", "top", "new", "rising", "comments"]
Time = Literal["hour", "day", "week", "month", "year", "all"]


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
        sort: Annotated[Sort, Field(description="Result ordering.")] = "new",
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

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

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
        try:
            items = await scrape_reddit(request, limit=max_items, on_item=heard)
        except RedditAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"Reddit refused anonymous access: {error}") from error
        return CallToolResult(
            content=[TextContent(type="text", text=_summary(items))],
            structured_content={"items": items},
        )

    return reddit


def _summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; the items themselves are in the structured result."""
    lines = [f"{len(items)} Reddit items"]
    for item in items:
        where = item.get("communityName") or item.get("username") or ""
        title = item.get("title") or (item.get("body") or "")[:120]
        lines.append(
            f"- [{item.get('dataType')}] {title} ({where}) {item.get('url') or ''}"
        )
    return "\n".join(lines)
