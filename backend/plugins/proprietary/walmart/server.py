"""SurfSense's Walmart plugin: public products, listings and reviews, behind the license."""

import functools
import itertools
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import quote_plus, urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle
from proprietary.walmart.schemas import WalmartReviewsInput, WalmartScrapeInput
from proprietary.walmart.scraper import scrape_products, scrape_reviews

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000
MAX_ITEMS_PER_SOURCE = 100
MAX_REVIEWS_PER_SOURCE = 5000
# Text past these adds little to an answer and crowds out other items: ten
# detailed products should fit the text's 32 KB with room to spare (at 500
# characters and every specification, ten measured 31.2 KB).
_DESCRIPTION_CHARS = 300
_SPECIFICATIONS = 15
_SAMPLE_REVIEWS = 2
_SAMPLE_TEXT_CHARS = 200
_SELLER_RESPONSE_CHARS = 200

access = shared_access()

ReviewSort = Literal["most-recent", "most-helpful", "rating-high", "rating-low"]


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Joins the shared pools' close at shutdown; Walmart has nothing free to warm."""
    async with lifecycle.lifespan():
        yield


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
                    "Open each listed product's page for its full details; slower. "
                    "Listings leave out the rating of products sold in variants, "
                    "so those need details for stars and review counts."
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
        await stage(ctx, "searching Walmart", total=expected)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {expected} products", done=count)

        async def fetching(message: str) -> None:
            await stage(ctx, message)

        request = WalmartScrapeInput(
            startUrls=start_urls,
            maxItemsPerStartUrl=max_items,
            includeDetails=include_details,
            includeReviewsSample=include_reviews_sample,
        )
        items = await scrape_products(
            request, limit=MAX_RESULTS, on_item=heard, on_stage=fetching
        )
        return tool_result(
            _summary(items, "products"),
            items,
            project=_product_fields,
            text_only=wants_text_only(ctx),
        )

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
        await stage(ctx, "fetching Walmart reviews", total=expected)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {expected} reviews", done=count)

        async def fetching(message: str) -> None:
            await stage(ctx, message)

        request = WalmartReviewsInput(
            itemIds=sources, maxReviews=max_reviews, sort=sort_by
        )
        items = await scrape_reviews(
            request, limit=expected, on_item=heard, on_stage=fetching
        )
        counts = _per_product(items)
        head = _summary(items, "reviews")
        if len(counts) > 1:
            # Says whose reviews the text runs out before.
            head += " (" + ", ".join(f"{n} for {i}" for i, n in counts.items()) + ")"
        return tool_result(
            head,
            items,
            # With one product, its id on every line is ~10% of the text.
            project=functools.partial(_review_fields, with_id=len(counts) > 1),
            text_only=wants_text_only(ctx),
        )

    return walmart


def _http_urls(urls: list[str]) -> list[str]:
    """Trimmed and otherwise unchanged; anything but an http(s) URL is refused."""
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


def _clip(text: Any, chars: int) -> Any:
    if isinstance(text, str) and len(text) > chars:
        return text[:chars] + "…"
    return text


def _summary(items: list[dict[str, Any]], kind: str) -> str:
    """The header line the agent reads first; each item follows as one JSON line.

    Failed inputs are items with an `error` key, as the scraper streams them.
    """
    errors = sum("error" in item for item in items)
    head = f"{len(items) - errors} Walmart {kind}"
    if errors:
        head += f", {errors} failed"
    # A listing card stands in when its product page failed to load.
    partial = sum("detailsError" in item for item in items)
    if partial:
        head += f"; {partial} listing card only (details failed)"
    return head


def _per_product(items: list[dict[str, Any]]) -> Counter[Any]:
    """Each product's review count, in input order."""
    return Counter(item.get("usItemId") for item in items if "error" not in item)


def _failure(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "error": item["error"],
        "errorDescription": item.get("errorDescription"),
        "input": item.get("input"),
    }


def _product_fields(item: dict[str, Any]) -> dict[str, Any]:
    """What an agent compares products on; images and raw variant nodes stay out."""
    if "error" in item:
        return _failure(item)
    price = item.get("price") or {}
    sample = item.get("reviewsSample") or {}
    fulfillment = item.get("fulfillment") or {}
    return {
        "usItemId": item.get("usItemId"),
        "name": item.get("name"),
        "brand": item.get("brand"),
        "price": price.get("value"),
        "listPrice": (item.get("listPrice") or {}).get("value"),
        "currency": item.get("currency") or price.get("currency"),
        "stars": item.get("stars"),
        "reviewsCount": item.get("reviewsCount"),
        "availability": item.get("availabilityStatus"),
        "seller": (item.get("seller") or {}).get("name"),
        "sponsored": item.get("sponsored"),
        "category": item.get("category"),
        "url": item.get("url"),
        "shortDescription": _clip(item.get("shortDescription"), _DESCRIPTION_CHARS),
        "longDescription": _clip(item.get("longDescription"), _DESCRIPTION_CHARS),
        "specifications": _first(item.get("specifications"), _SPECIFICATIONS),
        "fulfillment": {
            kind: {
                key: option.get(key)
                for key in ("availabilityStatus", "deliveryDate", "badge", "price")
            }
            for kind, option in fulfillment.items()
            if isinstance(option, dict)
        },
        "topReviews": [
            {
                "rating": review.get("rating"),
                "title": review.get("title"),
                "text": _clip(review.get("text"), _SAMPLE_TEXT_CHARS),
            }
            for review in (sample.get("topReviews") or [])[:_SAMPLE_REVIEWS]
        ],
        "detailsError": item.get("detailsError"),
    }


def _first(specs: Any, count: int) -> Any:
    """The first ``count`` entries of a name→value dict, in the page's order."""
    if isinstance(specs, dict) and len(specs) > count:
        return dict(itertools.islice(specs.items(), count))
    return specs


def _review_fields(item: dict[str, Any], *, with_id: bool = True) -> dict[str, Any]:
    """The review itself; the variant it is about only when not the one asked for.

    A whole rating reads as ``5``, not ``5.0``, no helpful votes as none, and
    the keys are short: small, but on every one of 200 lines.
    """
    if "error" in item:
        return _failure(item)
    other = item.get("reviewedItemId") not in (None, item.get("usItemId"))
    rating = item.get("rating")
    if isinstance(rating, float) and rating.is_integer():
        rating = int(rating)
    return {
        "usItemId": item.get("usItemId") if with_id else None,
        "rating": rating,
        "title": item.get("title"),
        "text": item.get("text"),
        "date": item.get("submissionTime"),
        "verified": item.get("verifiedPurchase"),
        "helpful": item.get("positiveFeedback") or None,
        "sellerResponse": _clip(item.get("sellerResponse"), _SELLER_RESPONSE_CHARS),
        "reviewedItemId": item.get("reviewedItemId") if other else None,
        "reviewedItemName": item.get("reviewedItemName") if other else None,
    }
