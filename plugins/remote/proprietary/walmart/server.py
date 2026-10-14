"""SurfSense's Walmart plugin: public products, listings and reviews, behind the license."""

from collections.abc import Callable
from typing import Annotated, Any, Literal
from urllib.parse import quote_plus, urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.license_check.license_access import LicenseAccess
from proprietary.walmart.schemas import WalmartReviewsInput, WalmartScrapeInput
from proprietary.walmart.scraper import scrape_products, scrape_reviews

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000
MAX_ITEMS_PER_SOURCE = 100
MAX_REVIEWS_PER_SOURCE = 5000

access = LicenseAccess()

ReviewSort = Literal["most-recent", "most-helpful", "rating-high", "rating-low"]


def server() -> MCPServer:
    walmart = MCPServer("walmart")

    @walmart.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Walmart URLs to scrape: a product (/ip/...), search (/search?q=), "
                    "category (/cp/...) or browse (/browse/...) page. Give these or "
                    "search_terms; at most 20 in all."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_terms: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description="Terms to search Walmart for, one search each.",
            ),
        ] = [],  # noqa: B006
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_ITEMS_PER_SOURCE,
                description="Most products per URL or search term.",
            ),
        ] = 10,
        include_details: Annotated[
            bool,
            Field(
                description=(
                    "Open each listed product's page for its full details; slower."
                )
            ),
        ] = True,
        include_reviews_sample: Annotated[
            bool,
            Field(description="Include the sample of reviews on each product's page."),
        ] = True,
    ) -> CallToolResult:
        """Scrape public Walmart product details, search/category listings, prices,
        sellers, variants, availability, and a sample of on-page reviews."""
        if not urls and not search_terms:
            raise ToolError("Give at least one of urls or search_terms.")
        if len(urls) + len(search_terms) > MAX_SOURCES:
            raise ToolError(
                f"Give no more than {MAX_SOURCES} urls and search_terms combined."
            )
        start_urls = [
            *_http_urls(urls),
            *(
                f"https://www.walmart.com/search?q={quote_plus(term)}"
                for term in search_terms
            ),
        ]
        expected = min(len(start_urls) * max_items, MAX_RESULTS)

        async def heard(count: int) -> None:
            await ctx.report_progress(count, expected)

        request = WalmartScrapeInput(
            startUrls=start_urls,
            maxItemsPerStartUrl=max_items,
            includeDetails=include_details,
            includeReviewsSample=include_reviews_sample,
        )
        items = await scrape_products(request, limit=MAX_RESULTS, on_item=heard)
        return _result(items, "products", _product_line)

    @walmart.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def reviews(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Walmart product URLs (/ip/...) or reviews URLs to fetch reviews "
                    "for. Give these or item_ids."
                ),
            ),
        ] = [],  # noqa: B006
        item_ids: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description="Walmart numeric item ids (usItemId) to fetch reviews for.",
            ),
        ] = [],  # noqa: B006
        max_reviews: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_REVIEWS_PER_SOURCE,
                description="Most reviews per product (10 per page).",
            ),
        ] = 200,
        sort_by: Annotated[ReviewSort, Field(description="Review ordering.")] = (
            "most-recent"
        ),
    ) -> CallToolResult:
        """Fetch deep paginated public Walmart product reviews with ratings, text,
        authors, verified-purchase flags, images, and seller responses."""
        if not urls and not item_ids:
            raise ToolError("Give at least one of urls or item_ids.")
        sources = [*_http_urls(urls), *item_ids]
        expected = len(sources) * max_reviews

        async def heard(count: int) -> None:
            await ctx.report_progress(count, expected)

        request = WalmartReviewsInput(
            itemIds=sources, maxReviews=max_reviews, sort=sort_by
        )
        items = await scrape_reviews(request, limit=expected, on_item=heard)
        return _result(items, "reviews", _review_line)

    return walmart


def _http_urls(urls: list[str]) -> list[str]:
    """Trimmed and otherwise unchanged; anything but an http(s) URL is refused."""
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


def _result(
    items: list[dict[str, Any]], kind: str, line: Callable[[dict[str, Any]], str]
) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=_summary(items, kind, line))],
        structured_content={"items": items},
    )


def _summary(
    items: list[dict[str, Any]], kind: str, line: Callable[[dict[str, Any]], str]
) -> str:
    """What the agent reads first; the items themselves are in the structured result.

    Failed inputs are items with an `error` key, as the scraper streams them.
    """
    errors = [item for item in items if "error" in item]
    head = f"{len(items) - len(errors)} Walmart {kind}"
    if errors:
        head += f", {len(errors)} failed"
    lines = [head]
    for item in items:
        if "error" in item:
            lines.append(
                f"- [{item['error']}] {item.get('errorDescription') or ''} "
                f"({item.get('input') or ''})"
            )
        else:
            lines.append(line(item))
    return "\n".join(lines)


def _product_line(item: dict[str, Any]) -> str:
    price = (item.get("price") or {}).get("value")
    cost = f" ${price}" if price is not None else ""
    return f"- {item.get('name')}{cost} {item.get('url') or ''}"


def _review_line(item: dict[str, Any]) -> str:
    said = item.get("title") or (item.get("text") or "")[:120]
    return (
        f"- {item.get('rating')}/5 {said} by {item.get('author')} "
        f"(item {item.get('usItemId')})"
    )
