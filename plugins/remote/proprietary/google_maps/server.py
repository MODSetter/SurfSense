"""SurfSense's Google Maps plugin: public places and their reviews, behind the license."""

from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from proprietary.google_maps.fetch import SignInRequiredError
from proprietary.google_maps.reviews import scrape_reviews
from proprietary.google_maps.schemas import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
)
from proprietary.google_maps.scraper import scrape_places
from proprietary.license_check.license_access import LicenseAccess

# Bounds one call's fan-out, as the scraper API's did.
MAX_SOURCES = 20
MAX_PLACES = 1000
MAX_REVIEWS = 100_000

access = LicenseAccess()

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

        async def heard(count: int) -> None:
            await ctx.report_progress(count)

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
            items = await scrape_places(request, on_item=heard)
        except SignInRequiredError as error:
            raise ToolError(_signin_refusal(error)) from error
        return _result(_places_summary(items), items)

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

        async def heard(count: int) -> None:
            await ctx.report_progress(count)

        request = GoogleMapsReviewsInput(
            startUrls=[{"url": url.strip()} for url in urls],
            placeIds=place_ids,
            maxReviews=max_reviews,
            reviewsSort=sort_by,
            reviewsStartDate=start_date,
            language=language,
        )
        try:
            items = await scrape_reviews(request, on_item=heard)
        except SignInRequiredError as error:
            raise ToolError(_signin_refusal(error)) from error
        return _result(_reviews_summary(items), items)

    return maps


def _check_urls(urls: list[str]) -> None:
    for url in urls:
        parts = urlsplit(url.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")


def _signin_refusal(error: SignInRequiredError) -> str:
    # Public Maps data needs no account: a wall means Google refused this address.
    return f"Google sign in required: {error}"


def _result(summary: str, items: list[dict[str, Any]]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content={"items": items},
    )


def _places_summary(items: list[dict[str, Any]]) -> str:
    """What the agent reads first; the items themselves are in the structured result."""
    lines = [f"{len(items)} Google Maps places"]
    for item in items:
        score = item.get("totalScore")
        count = item.get("reviewsCount")
        # A search result carries no count without details; never print it as 0.
        reviewed = f" ({count} reviews)" if count is not None else ""
        rating = f" {score} stars{reviewed}" if score else ""
        lines.append(
            f"- {item.get('title')}{rating}, {item.get('address') or ''} "
            f"{item.get('url') or ''}"
        )
    return "\n".join(lines)


def _reviews_summary(items: list[dict[str, Any]]) -> str:
    lines = [f"{len(items)} Google Maps reviews"]
    for item in items:
        text = (item.get("text") or "")[:120]
        lines.append(
            f"- [{item.get('stars')} stars] {item.get('name') or 'anonymous'} "
            f"on {item.get('title') or item.get('placeId') or ''}: {text}"
        )
    return "\n".join(lines)
