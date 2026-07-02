"""``youtube.comments`` capability registration (free — see 04-capabilities open item)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.youtube.comments.executor import build_comments_executor
from app.capabilities.youtube.comments.schemas import CommentsInput, CommentsOutput

YOUTUBE_COMMENTS = Capability(
    name="youtube.comments",
    description=(
        "Fetch public comments (and their replies) for one or more YouTube "
        "videos. Give it the video URLs; returns structured comment items with "
        "author, text, like count, reply relationships, and timestamps. Use it "
        "to gauge sentiment or pull discussion on specific videos."
    ),
    input_schema=CommentsInput,
    output_schema=CommentsOutput,
    executor=build_comments_executor(),
    billing_unit=None,
)

register_capability(YOUTUBE_COMMENTS)
