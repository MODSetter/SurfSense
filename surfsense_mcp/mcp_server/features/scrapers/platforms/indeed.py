"""Indeed scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

IndeedSort = Literal["relevance", "date"]
IndeedJobType = Literal[
    "fulltime",
    "parttime",
    "contract",
    "internship",
    "temporary",
    "permanent",
    "seasonal",
    "freelance",
]
IndeedLevel = Literal["entry_level", "mid_level", "senior_level"]
IndeedRemote = Literal["remote", "hybrid"]


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the Indeed tool."""

    @mcp.tool(
        name="surfsense_indeed_scrape",
        title="Search or scrape Indeed jobs",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def indeed_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Indeed URLs: a search page "
                "('https://www.indeed.com/jobs?q=data+analyst'), a company jobs "
                "page ('/cmp/<slug>/jobs'), or a single job ('/viewjob?jk=...'). "
                "Provide urls OR search_queries."
            ),
        ] = None,
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Job search terms, e.g. ['data analyst', 'ml engineer']. "
                "Provide search_queries OR urls."
            ),
        ] = None,
        country: Annotated[
            str,
            Field(description="Country code selecting the Indeed domain, e.g. 'us', 'gb'."),
        ] = "us",
        location: Annotated[
            str | None,
            Field(description="Where to search, e.g. 'Remote', 'New York, NY'."),
        ] = None,
        radius: Annotated[
            int | None,
            Field(description="Search radius in miles/km around location."),
        ] = None,
        job_type: Annotated[
            IndeedJobType | None,
            Field(description="Employment type filter."),
        ] = None,
        level: Annotated[
            IndeedLevel | None,
            Field(description="Experience level filter."),
        ] = None,
        remote: Annotated[
            IndeedRemote | None,
            Field(description="Work model filter: remote or hybrid."),
        ] = None,
        from_days: Annotated[
            int | None,
            Field(description="Only return jobs posted within the last N days."),
        ] = None,
        sort: Annotated[
            IndeedSort, Field(description="Result ordering: relevance or date.")
        ] = "relevance",
        scrape_job_details: Annotated[
            bool,
            Field(
                description="True fetches each job's detail page for the full "
                "description (slower); False returns the listing snippet only."
            ),
        ] = False,
        max_items: Annotated[
            int, Field(ge=1, description="Maximum jobs to return in total.")
        ] = 25,
        max_items_per_query: Annotated[
            int, Field(ge=0, description="Max jobs per search/company target.")
        ] = 25,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search or scrape public Indeed job postings.

        Use this for ANY Indeed job research — openings for a role, who is hiring
        at a company, salaries for a title in a location, or remote roles —
        instead of a generic web search. Returns jobs with title, company,
        location, salary, job types, and description; set scrape_job_details for
        the full description per job.
        Example: search_queries=['data analyst'], location='Remote', max_items=30.
        """
        return await run_scraper(
            client,
            context,
            platform="indeed",
            verb="scrape",
            payload={
                "urls": urls,
                "search_queries": search_queries,
                "country": country,
                "location": location,
                "radius": radius,
                "job_type": job_type,
                "level": level,
                "remote": remote,
                "from_days": from_days,
                "sort": sort,
                "scrape_job_details": scrape_job_details,
                "max_items": max_items,
                "max_items_per_query": max_items_per_query,
            },
            workspace=workspace,
            response_format=response_format,
        )
