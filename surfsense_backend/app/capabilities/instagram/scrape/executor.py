"""``instagram.scrape`` executor: verb input → scraper → media items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.instagram.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.instagram import (
    InstagramAccessBlockedError,
    InstagramScrapeInput,
    scrape_instagram,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_instagram

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = InstagramScrapeInput(
            resultsType=payload.result_type,
            directUrls=payload.urls,
            search=",".join(payload.search_queries),
            searchType=payload.search_type,
            resultsLimit=payload.max_per_target,
            onlyPostsNewerThan=payload.newer_than,
            skipPinnedPosts=payload.skip_pinned_posts,
            addParentData=payload.add_parent_data,
        )
        emit_progress(
            "starting",
            "Resolving Instagram targets",
            total=payload.max_items,
            unit="item",
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except InstagramAccessBlockedError as exc:
            # Anonymous-only scraper; a hard block can't be retried with creds.
            raise ForbiddenError(
                "Instagram requires a login for this request and SurfSense scrapes "
                "anonymously. Provide a profile URL or handle via directUrls; "
                "keyword/hashtag search needs an account and is unavailable. "
                f"Details: {exc}",
                code="INSTAGRAM_ACCESS_BLOCKED",
            ) from exc
        emit_progress(
            "done", f"Scraped {len(items)} item(s)", current=len(items), unit="item"
        )
        return ScrapeOutput(items=items)

    return execute
