"""SurfSense's Amazon plugin: public products, search results, offers and sellers, behind the license."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from urllib.parse import quote_plus, urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.amazon.schemas import AmazonScrapeInput
from proprietary.amazon.scraper import scrape_products
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle

# Bounds one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000
# What an agent reads of a product's lists before it would need a follow-up call.
_FEATURES_SHOWN = 5
_REVIEWS_SHOWN = 3
_OFFERS_SHOWN = 5
_SPECS_SHOWN = 6

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Closes the shared request pools at shutdown; Amazon has nothing to warm."""
    async with lifecycle.lifespan():
        yield


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

        await stage(ctx, "starting", total=expected)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {expected} items", done=count, total=expected)

        async def reached(message: str) -> None:
            await stage(ctx, message)

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
        notes: list[str] = []
        items = await scrape_products(
            request,
            limit=MAX_RESULTS,
            on_item=heard,
            on_stage=reached,
            notes=notes,
        )
        return tool_result(
            _summary(items, notes),
            items,
            project=_projected,
            text_only=wants_text_only(ctx),
        )

    return amazon


def _summary(items: list[dict[str, Any]], notes: list[str]) -> str:
    """The header line the agent reads first; one JSON line per item follows it."""
    products = sum("error" not in item for item in items)
    return "\n".join(
        [f"{products} Amazon products, {len(items) - products} errors", *notes]
    )


def _amount(price: Any) -> str | None:
    if not isinstance(price, dict) or price.get("value") is None:
        return None
    return f"{price['value']} {price.get('currency') or ''}".rstrip()


def _seller(seller: Any) -> dict[str, Any] | None:
    if not isinstance(seller, dict):
        return None
    return {
        "name": seller.get("name"),
        "rating": seller.get("averageRating"),
        "reviews": seller.get("reviewsCount"),
    }


def _product_url(item: dict[str, Any]) -> str | None:
    """The plain /dp/ link: search links carry a few hundred bytes of tracking."""
    url, asin = item.get("url"), item.get("asin")
    host = urlsplit(url).netloc if url else ""
    return f"https://{host}/dp/{asin}" if host and asin else url


def _specs(rows: Any) -> dict[str, Any] | None:
    """The first few product-overview rows ("Brand", "Color"...) as key: value."""
    specs = {
        row.get("name"): row.get("value")
        for row in (rows or [])[:_SPECS_SHOWN]
        if isinstance(row, dict) and row.get("name")
    }
    return specs or None


def _projected(item: dict[str, Any]) -> dict[str, Any]:
    """The fields an agent answers from: price, rating, description, reviews, offers."""
    if "error" in item:
        return {
            "error": item["error"],
            "description": item.get("errorDescription"),
            "input": item.get("input"),
        }
    card = item.get("categoryPageData") or {}
    ranked = item.get("bestsellerPageData") or {}
    return {
        "title": item.get("title"),
        "asin": item.get("asin"),
        # Set on variant items only; a product's own ASIN would just repeat.
        "originalAsin": (
            item.get("originalAsin")
            if item.get("originalAsin") != item.get("asin")
            else None
        ),
        "url": _product_url(item),
        "brand": item.get("brand"),
        "author": item.get("author"),
        "price": _amount(item.get("price")),
        "listPrice": _amount(item.get("listPrice")),
        "inStock": item.get("inStock"),
        "inStockText": item.get("inStockText"),
        "delivery": item.get("delivery"),
        "stars": item.get("stars"),
        "reviewsCount": item.get("reviewsCount"),
        "monthlyPurchaseVolume": item.get("monthlyPurchaseVolume"),
        "isAmazonChoice": item.get("isAmazonChoice") or None,
        "searchPosition": card.get("position"),
        "bestsellerRank": ranked.get("rank"),
        "bestsellerRanks": item.get("bestsellerRanks"),
        "description": item.get("description"),
        "features": (item.get("features") or [])[:_FEATURES_SHOWN],
        "specs": _specs(item.get("productOverview")),
        "reviewsSummary": (item.get("aiReviewsSummary") or {}).get("text"),
        "reviews": [
            {
                "stars": review.get("stars"),
                "title": review.get("title"),
                "text": review.get("text"),
            }
            for review in (item.get("productPageReviews") or [])[:_REVIEWS_SHOWN]
            if isinstance(review, dict)
        ],
        "seller": _seller(item.get("seller")),
        "offers": [
            {
                "price": _amount(offer.get("price")),
                "condition": offer.get("condition"),
                "delivery": offer.get("delivery"),
                "seller": _seller(offer.get("seller")),
            }
            for offer in (item.get("offers") or [])[:_OFFERS_SHOWN]
            if isinstance(offer, dict)
        ],
        "variants": [
            {"asin": detail.get("asin"), "price": _amount(detail.get("price"))}
            for detail in item.get("variantDetails") or []
            if isinstance(detail, dict) and detail.get("price")
        ],
        "locationText": item.get("locationText"),
    }
