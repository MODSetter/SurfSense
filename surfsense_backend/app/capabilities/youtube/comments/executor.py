"""``youtube.comments`` executor: verb input → scraper → comment items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.youtube.comments.schemas import CommentsInput, CommentsOutput
from app.proprietary.platforms.youtube import (
    YouTubeCommentsInput,
    scrape_comments,
)

CommentsFn = Callable[[YouTubeCommentsInput], Awaitable[list[dict]]]


def build_comments_executor(scrape_fn: CommentsFn | None = None) -> Executor:
    """Bind the executor to a comments scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_comments

    async def execute(payload: CommentsInput) -> CommentsOutput:
        actor_input = YouTubeCommentsInput(
            startUrls=[{"url": url} for url in payload.urls],
            maxComments=payload.max_comments,
            sortCommentsBy=payload.sort_by,
        )
        items = await scrape_fn(actor_input)
        return CommentsOutput(items=items)

    return execute
