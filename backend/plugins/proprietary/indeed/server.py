"""SurfSense's Indeed plugin: public job postings, behind the license."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import ELLIPSIS, tool_result, wants_text_only
from proprietary.indeed import fetch
from proprietary.indeed.fetch import IndeedAccessBlockedError
from proprietary.indeed.schemas import (
    IndeedJobType,
    IndeedLevel,
    IndeedRemote,
    IndeedScrapeInput,
    IndeedSort,
)
from proprietary.indeed.scraper import scrape_indeed
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_ITEMS = 100
# A description's share of the text, so 25 detailed jobs fit in it (at 2,000
# characters it was full after 13); the whole one is in the structured result.
DESCRIPTION_CHARS = 600

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Holds the shared scraping pools (the kept browser context) open while mounted.

    No warm-up: the first call's context needs a proxy exit, which costs credit.
    """
    async with lifecycle.lifespan():
        yield


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
                    "Also fetch each job's full description, pay and company "
                    "rating: one light request per job, about a second in all."
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

        await stage(ctx, "scraping Indeed", total=max_items)

        async def heard(count: int) -> None:
            await stage(
                ctx, f"{count} of {max_items} jobs", done=count, total=max_items
            )

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
        # Page loads, solves and rotations report too, so a slow call is not silent.
        token = fetch.on_stage.set(lambda message: stage(ctx, message))
        try:
            items = await scrape_indeed(request, limit=max_items, on_item=heard)
        except IndeedAccessBlockedError as error:
            # Anonymous only: a refusal after every address was tried cannot be retried.
            raise ToolError(f"Indeed refused anonymous access: {error}") from error
        finally:
            fetch.on_stage.reset(token)
        return tool_result(
            _summary(items),
            items,
            project=_projected,
            text_only=wants_text_only(ctx),
        )

    return indeed


def _summary(items: list[dict[str, Any]]) -> str:
    """The header line; each job follows it as one line of JSON."""
    detailed = sum(1 for item in items if item.get("descriptionHtml"))
    return f"{len(items)} Indeed jobs" + (
        f", {detailed} with full descriptions" if detailed else ""
    )


def _projected(item: dict[str, Any]) -> dict[str, Any]:
    """What an agent needs to answer from a job without opening it.

    Tracking links, the description HTML and the scrape stamp stay in the
    structured result.
    """
    salary = item.get("salary") or {}
    return {
        "title": item.get("title"),
        "company": item.get("company"),
        "location": item.get("formattedLocation"),
        "remote": item.get("remoteType") or (True if item.get("isRemote") else None),
        "salary": salary.get("salaryText"),
        "salaryMin": salary.get("salaryMin"),
        "salaryMax": salary.get("salaryMax"),
        "currency": salary.get("currency"),
        "period": salary.get("period"),
        "salaryEstimated": salary.get("isEstimated") or None,
        "jobTypes": item.get("jobTypes"),
        "benefits": item.get("benefits"),
        "companyRating": item.get("companyRating"),
        "companyReviewCount": item.get("companyReviewCount"),
        "posted": item.get("age") or item.get("datePublished"),
        "jobUrl": item.get("jobUrl"),
        "companyUrl": item.get("companyUrl"),
        "description": _clipped(item.get("descriptionText"), DESCRIPTION_CHARS),
    }


def _clipped(text: Any, chars: int) -> Any:
    """``text`` cut to ``chars`` with an ellipsis, as the reply clips long strings."""
    if isinstance(text, str) and len(text) > chars:
        return text[:chars] + ELLIPSIS
    return text
