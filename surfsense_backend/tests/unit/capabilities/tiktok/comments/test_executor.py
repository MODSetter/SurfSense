"""``tiktok.comments`` executor: verb input → scraper args → typed comment items.

Boundary mocked: the proprietary comments actor (injected fake). NOT mocked: the
verb's own payload→args forwarding and the dict→CommentItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.tiktok.comments.executor import build_comments_executor
from app.capabilities.tiktok.comments.schemas import CommentsInput, CommentsOutput

pytestmark = pytest.mark.unit

_VIDEO = "https://www.tiktok.com/@bob/video/123"


class _FakeComments:
    """Records the urls + kwargs it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[list[str], int, int | None]] = []

    async def __call__(
        self, video_urls: list[str], *, per_video: int, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((video_urls, per_video, limit))
        return self._items


async def test_forwards_urls_and_limits_and_wraps_items():
    comments = _FakeComments([{"id": "1", "text": "hi"}])
    execute = build_comments_executor(comments_fn=comments)

    out = await execute(
        CommentsInput(video_urls=[_VIDEO], comments_per_video=15, max_items=40)
    )

    assert isinstance(out, CommentsOutput)
    assert len(out.items) == 1
    assert out.items[0].text == "hi"

    (urls, per_video, limit) = comments.calls[0]
    assert urls == [_VIDEO]
    assert per_video == 15
    assert limit == 40
