"""Google Maps scraper tools: places and reviews."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

ReviewSort = Literal["newest", "mostRelevant", "highestRanking", "lowestRanking"]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the Google Maps place and review tools."""

    @mcp.tool(
        name="surfsense_google_maps_scrape",
        title="Find places on Google Maps",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def google_maps_scrape(
        search_queries: Annotated[
            list[str] | None,
            Field(
                description="Place searches, e.g. ['coffee shops']. Provide "
                "search_queries OR urls OR place_ids."
            ),
        ] = None,
        urls: Annotated[
            list[str] | None,
            Field(description="Google Maps URLs of specific places."),
        ] = None,
        place_ids: Annotated[
            list[str] | None,
            Field(description="Google place ids, e.g. ['ChIJj61dQgK6j4AR...']."),
        ] = None,
        location: Annotated[
            str | None,
            Field(
                description="Geographic scope for a search, e.g. "
                "'Seattle, USA'."
            ),
        ] = None,
        max_places: Annotated[
            int, Field(ge=1, description="Maximum places to return.")
        ] = 10,
        include_details: Annotated[
            bool,
            Field(
                description="True adds opening hours and extra contact info "
                "(slower)."
            ),
        ] = False,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Find places on Google Maps by search, URL, or place id.

        Use this for local-business and location research: names, addresses,
        ratings, categories, coordinates, place ids. For a place's customer
        reviews use surfsense_google_maps_reviews instead.
        Example: search_queries=['ramen'], location='Osaka, Japan', max_places=5.
        """
        return await run_scraper(
            client,
            context,
            platform="google_maps",
            verb="scrape",
            payload={
                "search_queries": search_queries,
                "urls": urls,
                "place_ids": place_ids,
                "location": location,
                "max_places": max_places,
                "include_details": include_details,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_google_maps_reviews",
        title="Fetch Google Maps reviews",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def google_maps_reviews(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Google Maps URLs of places. Provide urls OR "
                "place_ids."
            ),
        ] = None,
        place_ids: Annotated[
            list[str] | None,
            Field(
                description="Google place ids from surfsense_google_maps_scrape."
            ),
        ] = None,
        max_reviews: Annotated[
            int, Field(ge=1, description="Maximum reviews per place.")
        ] = 20,
        sort_by: Annotated[
            ReviewSort, Field(description="Review ordering.")
        ] = "newest",
        language: Annotated[
            str, Field(description="Reviews language code, e.g. 'en'.")
        ] = "en",
        start_date: Annotated[
            str | None,
            Field(
                description="ISO date like '2026-01-01'; keeps only reviews on "
                "or after that day."
            ),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch customer reviews for Google Maps places by URL or place id.

        Use this to read feedback on specific places; get urls or place_ids
        from surfsense_google_maps_scrape first if you only have a name.
        Returns review text, rating, author, and date per review.
        Example: place_ids=['ChIJj61dQgK6j4AR...'], sort_by='newest'.
        """
        return await run_scraper(
            client,
            context,
            platform="google_maps",
            verb="reviews",
            payload={
                "urls": urls,
                "place_ids": place_ids,
                "max_reviews": max_reviews,
                "sort_by": sort_by,
                "language": language,
                "start_date": start_date,
            },
            workspace=workspace,
            response_format=response_format,
        )
