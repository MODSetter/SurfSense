"""``instagram.comments`` executor: verb input → scraper → comment items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.instagram.comments.schemas import CommentsInput, CommentsOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.instagram import (
    InstagramAccessBlockedError,
    InstagramScrapeInput,
    scrape_instagram,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_comments_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_instagram

    async def execute(payload: CommentsInput) -> CommentsOutput:
        actor_input = InstagramScrapeInput(
            resultsType="comments",
            directUrls=payload.urls,
            resultsLimit=payload.max_comments_per_post,
            isNewestComments=payload.newest_first,
            includeNestedComments=payload.include_replies,
        )
        emit_progress(
            "starting",
            "Fetching Instagram comments",
            total=payload.max_items,
            unit="comment",
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except InstagramAccessBlockedError as exc:
            raise ForbiddenError(
                f"Instagram refused anonymous access: {exc}",
                code="INSTAGRAM_ACCESS_BLOCKED",
            ) from exc
        emit_progress(
            "done",
            f"Scraped {len(items)} comment(s)",
            current=len(items),
            unit="comment",
        )
        return CommentsOutput(items=items)

    return execute
