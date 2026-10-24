"""SurfSense's Google Maps plugin: public places and their reviews, behind the license."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import tool_result, wants_text_only
from proprietary.google_maps.fetch import GoogleRefusedError, SignInRequiredError
from proprietary.google_maps.reviews import scrape_reviews
from proprietary.google_maps.schemas import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
)
from proprietary.google_maps.scraper import scrape_places
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle

# Bounds one call's fan-out, as the scraper API's did.
MAX_SOURCES = 20
MAX_PLACES = 1000
MAX_REVIEWS = 100_000

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Holds the shared pools (kept sessions) open until the host stops.

    Nothing to warm: a warm-up here would spend proxy credit while idle.
    """
    async with lifecycle.lifespan():
        yield


ReviewSort = Literal["newest", "mostRelevant", "highestRanking", "lowestRanking"]


def server() -> MCPServer:
    maps = MCPServer("google-maps")

    @maps.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Google Maps search terms, such as 'coffee shops'; each returns "
                    "up to max_places. Give these, urls or place_ids. Pair with "
                    "location to scope a search."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Google Maps URLs: a place page (/maps/place/...) or a search "
                    "results URL. Give these, search_queries or place_ids."
                ),
            ),
        ] = [],  # noqa: B006
        place_ids: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Known Google place IDs (ChIJ...) to fetch directly. Give these, "
                    "search_queries or urls."
                ),
            ),
        ] = [],  # noqa: B006
        location: Annotated[
            str | None,
            Field(
                description="Where to scope search_queries, such as 'New York, USA'."
            ),
        ] = None,
        max_places: Annotated[
            int,
            Field(ge=1, le=MAX_PLACES, description="Most places per search query."),
        ] = 10,
        language: Annotated[
            str, Field(description="Result language code, such as 'en' or 'fr'.")
        ] = "en",
        include_details: Annotated[
            bool,
            Field(
                description=(
                    "Also fetch each place's detail page: opening hours, popular "
                    "times, more contact details. Slower."
                )
            ),
        ] = False,
        max_reviews: Annotated[
            int,
            Field(ge=0, le=MAX_REVIEWS, description="Reviews per place; 0 for none."),
        ] = 0,
        max_images: Annotated[
            int, Field(ge=0, description="Images per place; 0 for none.")
        ] = 0,
    ) -> CallToolResult:
        """Scrape public Google Maps places, details, reviews and photos."""
        if not (search_queries or urls or place_ids):
            raise ToolError("Give at least one of search_queries, urls or place_ids.")
        _check_urls(urls)
        # At most: max_places per search (a URL may be one), one per place ID.
        expected = max_places * (len(search_queries) + len(urls)) + len(place_ids)
        await stage(ctx, "looking up places", total=expected)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} places", done=count, total=expected)

        async def staged(message: str) -> None:
            await stage(ctx, message)

        request = GoogleMapsScrapeInput(
            searchStringsArray=search_queries,
            startUrls=[{"url": url.strip()} for url in urls],
            placeIds=place_ids,
            locationQuery=location,
            maxCrawledPlacesPerSearch=max_places,
            language=language,
            scrapePlaceDetailPage=include_details,
            maxReviews=max_reviews,
            maxImages=max_images,
        )
        try:
            items = await scrape_places(request, on_item=heard, on_stage=staged)
        except SignInRequiredError as error:
            raise ToolError(_signin_refusal(error)) from error
        except GoogleRefusedError as error:
            raise ToolError(str(error)) from error
        return tool_result(
            _summary(items, "places"),
            items,
            project=_place_projected,
            text_only=wants_text_only(ctx),
        )

    @maps.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def reviews(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Google Maps place URLs to fetch reviews for. Give these or "
                    "place_ids."
                ),
            ),
        ] = [],  # noqa: B006
        place_ids: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Known Google place IDs (ChIJ...) to fetch reviews for. Give "
                    "these or urls."
                ),
            ),
        ] = [],  # noqa: B006
        max_reviews: Annotated[
            int, Field(ge=1, le=MAX_REVIEWS, description="Most reviews per place.")
        ] = 20,
        sort_by: Annotated[ReviewSort, Field(description="Review ordering.")] = (
            "newest"
        ),
        language: Annotated[
            str, Field(description="Review language code, such as 'en' or 'fr'.")
        ] = "en",
        start_date: Annotated[
            str | None,
            Field(description="ISO date: only reviews on or after it, '2024-01-01'."),
        ] = None,
    ) -> CallToolResult:
        """Fetch public Google Maps reviews: authors, ratings, text, owner replies."""
        if not (urls or place_ids):
            raise ToolError("Give at least one of urls or place_ids.")
        _check_urls(urls)
        expected = max_reviews * (len(urls) + len(place_ids))
        await stage(ctx, "looking up places", total=expected)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} reviews", done=count, total=expected)

        async def staged(message: str) -> None:
            await stage(ctx, message)

        request = GoogleMapsReviewsInput(
            startUrls=[{"url": url.strip()} for url in urls],
            placeIds=place_ids,
            maxReviews=max_reviews,
            reviewsSort=sort_by,
            reviewsStartDate=start_date,
            language=language,
        )
        try:
            items = await scrape_reviews(request, on_item=heard, on_stage=staged)
        except SignInRequiredError as error:
            raise ToolError(_signin_refusal(error)) from error
        except GoogleRefusedError as error:
            raise ToolError(str(error)) from error
        return tool_result(
            _summary(items, "reviews"),
            items,
            project=_review_projected,
            text_only=wants_text_only(ctx),
        )

    return maps


def _check_urls(urls: list[str]) -> None:
    for url in urls:
        parts = urlsplit(url.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")


def _signin_refusal(error: SignInRequiredError) -> str:
    # Public Maps data needs no account: a wall means Google refused this address.
    return f"Google sign in required: {error}"


def _summary(items: list[dict[str, Any]], what: str) -> str:
    """The header line; the items follow it, one per line."""
    errors = sum(1 for item in items if "error" in item)
    sources = "source" if errors == 1 else "sources"
    failed = f", {errors} {sources} failed" if errors else ""
    return f"{len(items) - errors} Google Maps {what}{failed}"


def _error_projected(item: dict[str, Any]) -> dict[str, Any]:
    return {"error": item["error"], "input": item.get("input")}


def _place_projected(item: dict[str, Any]) -> dict[str, Any]:
    """What an agent needs to answer about a place without asking again."""
    if "error" in item:
        return _error_projected(item)
    return {
        "title": item.get("title"),
        "category": item.get("categoryName"),
        "address": item.get("address"),
        "rating": item.get("totalScore"),
        # A search result carries no count without details: left out, never 0.
        "reviewsCount": item.get("reviewsCount"),
        "price": item.get("price"),
        "phone": item.get("phone"),
        "website": item.get("website"),
        "permanentlyClosed": item.get("permanentlyClosed") or None,
        "temporarilyClosed": item.get("temporarilyClosed") or None,
        "description": item.get("description"),
        "openingHours": [
            f"{hours.get('day')}: {hours.get('hours')}"
            for hours in item.get("openingHours") or []
        ],
        "reviewsTags": [
            f"{tag.get('title')} ({tag.get('count')})"
            for tag in item.get("reviewsTags") or []
        ],
        "imageUrls": item.get("imageUrls"),
        "reviews": [_review_fields(review) for review in item.get("reviews") or []],
        "placeId": item.get("placeId"),
        "url": item.get("url"),
    }


def _review_fields(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": review.get("name"),
        "stars": review.get("stars"),
        "date": review.get("publishedAtDate"),
        "text": review.get("text"),
        "textTranslated": review.get("textTranslated"),
        "ownerReply": review.get("responseFromOwnerText"),
    }


def _review_projected(item: dict[str, Any]) -> dict[str, Any]:
    if "error" in item:
        return _error_projected(item)
    return {"place": item.get("title"), **_review_fields(item)}
