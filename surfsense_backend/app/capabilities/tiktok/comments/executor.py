"""``tiktok.comments`` executor: video URLs -> scraper -> TikTok comment items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.tiktok.comments.schemas import CommentsInput, CommentsOutput
from app.proprietary.platforms.tiktok import scrape_tiktok_comments

CommentsFn = Callable[..., Awaitable[list[dict]]]


def build_comments_executor(comments_fn: CommentsFn | None = None) -> Executor:
    """Bind the executor to a comments fn (defaults to the proprietary actor)."""
    comments_fn = comments_fn or scrape_tiktok_comments

    async def execute(payload: CommentsInput) -> CommentsOutput:
        emit_progress(
            "starting",
            "Scraping TikTok comments",
            total=payload.max_items,
            unit="item",
        )
        items = await comments_fn(
            payload.video_urls,
            per_video=payload.comments_per_video,
            limit=payload.max_items,
        )
        emit_progress(
            "done", f"Scraped {len(items)} comment(s)", current=len(items), unit="item"
        )
        return CommentsOutput(items=items)

    return execute
