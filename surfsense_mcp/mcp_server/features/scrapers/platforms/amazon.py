"""Amazon product scraper tool."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import SurfSenseClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the Amazon product tool."""

    @mcp.tool(
        name="surfsense_amazon_scrape",
        title="Scrape Amazon products",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def amazon_scrape(
        urls: Annotated[
            list[str] | None,
            Field(
                description="Amazon product, search, category, best-seller, or short "
                "(a.co / amzn.to) URLs. Provide urls OR search_terms."
            ),
        ] = None,
        search_terms: Annotated[
            list[str] | None,
            Field(
                description="Search phrases run on the Amazon domain, e.g. "
                "['wireless earbuds']. Provide search_terms OR urls."
            ),
        ] = None,
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=100,
                description="Max products per search term or category/best-seller URL.",
            ),
        ] = 10,
        domain: Annotated[
            str,
            Field(
                description="Amazon marketplace domain, e.g. 'www.amazon.com', "
                "'www.amazon.co.uk'."
            ),
        ] = "www.amazon.com",
        include_details: Annotated[
            bool,
            Field(
                description="Fetch full product detail pages. False returns faster "
                "card-only results from search/category listings."
            ),
        ] = True,
        max_offers: Annotated[
            int,
            Field(
                ge=0,
                le=100,
                description="Extra marketplace offers to fetch per product. "
                "0 returns the featured offer only.",
            ),
        ] = 0,
        include_sellers: Annotated[
            bool,
            Field(
                description="Enrich the featured product and each offer with the "
                "seller's public profile summary."
            ),
        ] = False,
        max_variants: Annotated[
            int,
            Field(
                ge=0,
                le=100,
                description="Product variants (e.g. colors, sizes) to return as "
                "separate results. 0 disables variant expansion.",
            ),
        ] = 0,
        include_variant_prices: Annotated[
            bool,
            Field(
                description="Attach per-variant prices (one extra request per variant)."
            ),
        ] = False,
        country_code: Annotated[
            str | None,
            Field(description="Two-letter delivery country for localized pricing, "
            "e.g. 'us'."),
        ] = None,
        zip_code: Annotated[
            str | None,
            Field(
                description="Delivery ZIP/postal code for localized availability and "
                "pricing, e.g. '10001'."
            ),
        ] = None,
        language: Annotated[
            str | None,
            Field(description="Content language for the domain, e.g. 'en'."),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Scrape public Amazon product data by URL or search term.

        Use this for product research: title, price, list price, rating and
        review breakdown, availability, images, features, best-seller ranks,
        marketplace offers, sellers, and on-page reviews. Only public,
        anonymous data — no login. Provide search_terms to discover products
        or urls to target specific products, searches, categories, or
        best-seller pages.
        Example: search_terms=['mechanical keyboard'], domain='www.amazon.com',
        max_items=5, max_offers=3.
        """
        return await run_scraper(
            client,
            context,
            platform="amazon",
            verb="scrape",
            payload={
                "urls": urls,
                "search_terms": search_terms,
                "max_items": max_items,
                "domain": domain,
                "include_details": include_details,
                "max_offers": max_offers,
                "include_sellers": include_sellers,
                "max_variants": max_variants,
                "include_variant_prices": include_variant_prices,
                "country_code": country_code,
                "zip_code": zip_code,
                "language": language,
            },
            workspace=workspace,
            response_format=response_format,
        )
