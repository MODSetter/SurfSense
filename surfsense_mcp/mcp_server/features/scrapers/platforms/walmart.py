"""Walmart scraper tools: products/listings and deep reviews."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

ReviewSort = Literal["most-recent", "most-helpful", "rating-high", "rating-low"]


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the Walmart product and review tools."""

    @mcp.tool(
        name="surfsense_walmart_scrape",
        title="Scrape Walmart products",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def walmart_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Walmart product (/ip/), search (/search), category "
                "(/cp/), or browse (/browse/) URLs. Provide urls OR search_terms."
            ),
        ] = None,
        search_terms: Annotated[
            list[str] | None,
            Field(
                description="Search phrases run on walmart.com, e.g. ['air fryer']. "
                "Provide search_terms OR urls."
            ),
        ] = None,
        max_items: Annotated[
            int,
            Field(ge=1, le=100, description="Max products per search term or listing URL."),
        ] = 10,
        include_details: Annotated[
            bool,
            Field(
                description="Fetch full product detail pages. False returns faster "
                "card-only results from listings."
            ),
        ] = True,
        include_reviews_sample: Annotated[
            bool,
            Field(
                description="Include the free on-page review sample (rating "
                "distribution, aspects, top reviews) on detail pages."
            ),
        ] = True,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape public Walmart product data by URL or search term.

        Use this for product research: title, price, list price, rating and
        review count, availability, seller (Walmart 1P vs marketplace), images,
        description, variants, and a sample of on-page reviews. Only public,
        anonymous data — no login. For a product's full review history use
        surfsense_walmart_reviews instead.
        Example: search_terms=['air fryer'], max_items=5.
        """
        return await run_scraper(
            client,
            context,
            platform="walmart",
            verb="scrape",
            payload={
                "urls": urls,
                "search_terms": search_terms,
                "max_items": max_items,
                "include_details": include_details,
                "include_reviews_sample": include_reviews_sample,
            },
            workspace=workspace,
            response_format=response_format,
        )

    @mcp.tool(
        name="surfsense_walmart_reviews",
        title="Fetch Walmart reviews",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def walmart_reviews(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Walmart product URLs (/ip/...). Provide urls OR item_ids."
            ),
        ] = None,
        item_ids: Annotated[
            list[str] | None,
            Field(
                description="Walmart numeric item ids (usItemId) from "
                "surfsense_walmart_scrape."
            ),
        ] = None,
        max_reviews: Annotated[
            int,
            Field(ge=1, le=5000, description="Max reviews per product (10 per page)."),
        ] = 200,
        sort_by: Annotated[
            ReviewSort, Field(description="Review ordering.")
        ] = "most-recent",
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch deep paginated customer reviews for Walmart products.

        Use this to read the full review history on specific products; get urls
        or item_ids from surfsense_walmart_scrape first if you only have a name.
        Returns rating, title, text, author, verified-purchase flag, images, and
        seller response per review.
        Example: item_ids=['212092810'], sort_by='most-helpful', max_reviews=100.
        """
        return await run_scraper(
            client,
            context,
            platform="walmart",
            verb="reviews",
            payload={
                "urls": urls,
                "item_ids": item_ids,
                "max_reviews": max_reviews,
                "sort_by": sort_by,
            },
            workspace=workspace,
            response_format=response_format,
        )
