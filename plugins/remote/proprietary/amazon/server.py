"""SurfSense's Amazon plugin: public products, search results, offers and sellers, behind the license."""

from typing import Annotated, Any
from urllib.parse import quote_plus, urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.amazon.schemas import AmazonScrapeInput
from proprietary.amazon.scraper import scrape_products
from proprietary.license_check.license_access import LicenseAccess

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000

access = LicenseAccess()


def server() -> MCPServer:
    amazon = MCPServer("amazon")

    @amazon.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Amazon URLs to scrape: a product (/dp/<ASIN>), a search or "
                    "category page (/s?k=...), a best-sellers page (/zgbs/...), or a "
                    "short link (a.co, amzn.to). Give these or search_terms."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_terms: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description="Search terms to run on the Amazon site given by domain.",
            ),
        ] = [],  # noqa: B006
        max_items: Annotated[
            int,
            Field(ge=1, le=100, description="Most products per URL or search term."),
        ] = 10,
        domain: Annotated[
            str,
            Field(
                pattern=r"^(?:www\.)?amazon\.[a-z.]+$",
                description="The Amazon site search_terms run on, such as www.amazon.de.",
            ),
        ] = "www.amazon.com",
        language: Annotated[
            str | None, Field(description="Language for the pages, such as 'en'.")
        ] = None,
        country_code: Annotated[
            str | None,
            Field(
                min_length=2,
                max_length=2,
                description="Two-letter delivery country, used with zip_code.",
            ),
        ] = None,
        zip_code: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=20,
                description="Delivery postcode, for local prices and availability.",
            ),
        ] = None,
        include_details: Annotated[
            bool,
            Field(
                description=(
                    "Open each product page from a search for its full details; "
                    "off returns the search cards only, faster."
                )
            ),
        ] = True,
        max_offers: Annotated[
            int, Field(ge=0, le=100, description="Most seller offers per product.")
        ] = 0,
        include_sellers: Annotated[
            bool, Field(description="Add each seller's rating and review count.")
        ] = False,
        max_variants: Annotated[
            int,
            Field(
                ge=0,
                le=100,
                description="Most variants (sizes, colours) per product as their own items.",
            ),
        ] = 0,
        include_variant_prices: Annotated[
            bool, Field(description="Add each variant's price to its product.")
        ] = False,
    ) -> CallToolResult:
        """Scrape public Amazon product details, search results, offers, sellers, best-seller rankings and on-page reviews."""
        if not urls and not search_terms:
            raise ToolError("Give at least one of urls or search_terms.")
        if len(urls) + len(search_terms) > MAX_SOURCES:
            raise ToolError(
                f"Give no more than {MAX_SOURCES} urls and search_terms combined."
            )
        for url in urls:
            parts = urlsplit(url.strip())
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ToolError(f"Not an http(s) URL: {url}")

        # Worst case within the per-call ceiling, as the scraper API estimated it.
        expected = min(
            len(search_terms) * max_items + len(urls) * (1 + max_variants),
            MAX_RESULTS,
        )

        async def heard(count: int) -> None:
            await ctx.report_progress(count, expected)

        search_urls = [
            f"https://{domain}/s?k={quote_plus(term)}" for term in search_terms
        ]
        request = AmazonScrapeInput(
            categoryOrProductUrls=[
                {"url": url} for url in [*(url.strip() for url in urls), *search_urls]
            ],
            maxItemsPerStartUrl=max_items,
            language=language,
            countryCode=country_code,
            zipCode=zip_code,
            scrapeProductDetails=include_details,
            maxOffers=max_offers,
            scrapeSellers=include_sellers,
            maxProductVariantsAsSeparateResults=max_variants,
            scrapeProductVariantPrices=include_variant_prices,
        )
        # A blocked or missing page comes back as an error item, not a raise.
        items = await scrape_products(request, limit=MAX_RESULTS, on_item=heard)
        return CallToolResult(
            content=[TextContent(type="text", text=_summary(items))],
            structured_content={"items": items},
        )

    return amazon


def _summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; the items themselves are in the structured result."""
    products = sum("error" not in item for item in items)
    lines = [f"{products} Amazon products, {len(items) - products} errors"]
    for item in items:
        if "error" in item:
            lines.append(
                f"- [error: {item['error']}] {item.get('errorDescription') or ''} "
                f"{item.get('input') or ''}"
            )
            continue
        price = item.get("price") or {}
        cost = (
            f" {price.get('value')} {price.get('currency') or ''}".rstrip()
            if price.get("value") is not None
            else ""
        )
        lines.append(
            f"- {item.get('title')} ({item.get('asin')}){cost} {item.get('url') or ''}"
        )
    return "\n".join(lines)
