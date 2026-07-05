"""``reddit.scrape`` executor: verb input → scraper → Reddit items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.reddit.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.reddit import (
    RedditAccessBlockedError,
    RedditScrapeInput,
    scrape_reddit,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_reddit

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = RedditScrapeInput(
            startUrls=[{"url": url} for url in payload.urls],
            searches=payload.search_queries,
            searchCommunityName=payload.community,
            sort=payload.sort,
            time=payload.time_filter,
            includeNSFW=payload.include_nsfw,
            skipComments=payload.skip_comments,
            maxItems=payload.max_items,
            maxPostCount=payload.max_posts,
            maxComments=payload.max_comments,
            postDateLimit=payload.post_date_limit,
            commentDateLimit=payload.comment_date_limit,
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except RedditAccessBlockedError as exc:
            # Anonymous-only scraper; a hard block can't be retried with creds.
            # Mirror google_maps' SignInRequiredError -> ForbiddenError mapping.
            raise ForbiddenError(
                f"Reddit refused anonymous access: {exc}",
                code="REDDIT_ACCESS_BLOCKED",
            ) from exc
        return ScrapeOutput(items=items)

    return execute
