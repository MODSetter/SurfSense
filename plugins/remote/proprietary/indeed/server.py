"""SurfSense's Indeed plugin: public job postings, behind the license."""

from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.indeed.fetch import IndeedAccessBlockedError
from proprietary.indeed.schemas import (
    IndeedJobType,
    IndeedLevel,
    IndeedRemote,
    IndeedScrapeInput,
    IndeedSort,
)
from proprietary.indeed.scraper import scrape_indeed
from proprietary.license_check.license_access import LicenseAccess

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100

access = LicenseAccess()


def server() -> MCPServer:
    indeed = MCPServer("indeed")

    @indeed.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Indeed URLs to scrape: a search page (/jobs?q=&l=), a company "
                    "jobs page (/cmp/<slug>/jobs) or a job (/viewjob?jk=). Give "
                    "these or search_queries."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Job search terms; each returns up to max_items_per_query "
                    "results, shaped by country, location, job_type and the rest."
                ),
            ),
        ] = [],  # noqa: B006
        country: Annotated[
            str,
            Field(
                description="Country code choosing the Indeed site: 'us', 'gb', 'de'."
            ),
        ] = "us",
        location: Annotated[
            str | None,
            Field(description="Where to search, such as 'Remote' or 'New York, NY'."),
        ] = None,
        radius: Annotated[
            int | None,
            Field(description="Search radius in miles or km around location."),
        ] = None,
        job_type: Annotated[
            IndeedJobType | None,
            Field(
                description="Employment type: fulltime, parttime, contract and so on."
            ),
        ] = None,
        level: Annotated[
            IndeedLevel | None,
            Field(
                description="Experience level: entry_level, mid_level, senior_level."
            ),
        ] = None,
        remote: Annotated[
            IndeedRemote | None, Field(description="Work model: remote or hybrid.")
        ] = None,
        from_days: Annotated[
            int | None, Field(description="Only jobs posted within the last N days.")
        ] = None,
        sort: Annotated[
            IndeedSort, Field(description="Result ordering: relevance or date.")
        ] = "relevance",
        scrape_job_details: Annotated[
            bool,
            Field(
                description=(
                    "Fetch each job's page for the full description: slower, one "
                    "more page load per job."
                )
            ),
        ] = False,
        max_items: Annotated[
            int,
            Field(ge=1, le=MAX_ITEMS, description="Most jobs to return in all."),
        ] = 25,
        max_items_per_query: Annotated[
            int, Field(ge=0, description="Most jobs per search or company page.")
        ] = 25,
    ) -> CallToolResult:
        """Scrape public Indeed job postings: title, company, location, salary and description."""
        if not urls and not search_queries:
            raise ToolError("Give at least one of urls or search_queries.")
        for url in urls:
            parts = urlsplit(url.strip())
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ToolError(f"Not an http(s) URL: {url}")

        async def heard(count: int) -> None:
            await ctx.report_progress(count, max_items)

        request = IndeedScrapeInput(
            startUrls=[{"url": url.strip()} for url in urls],
            queries=search_queries,
            country=country,
            location=location,
            radius=radius,
            jobType=job_type,
            level=level,
            remote=remote,
            fromDays=from_days,
            sort=sort,
            scrapeJobDetails=scrape_job_details,
            maxItems=max_items,
            maxItemsPerQuery=max_items_per_query,
        )
        try:
            items = await scrape_indeed(request, limit=max_items, on_item=heard)
        except IndeedAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"Indeed refused anonymous access: {error}") from error
        return CallToolResult(
            content=[TextContent(type="text", text=_summary(items))],
            structured_content={"items": items},
        )

    return indeed


def _summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; each job whole is in the structured result."""
    lines = [f"{len(items)} Indeed jobs"]
    for item in items:
        lines.append(
            f"- {item.get('title')}, {item.get('company')}, "
            f"{item.get('formattedLocation')} {item.get('jobUrl') or ''}"
        )
    return "\n".join(lines)
