"""``youtube.comments`` capability registration (billed per comment; see config
``YOUTUBE_MICROS_PER_COMMENT``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.youtube.comments.executor import build_comments_executor
from app.capabilities.youtube.comments.schemas import CommentsInput, CommentsOutput

YOUTUBE_COMMENTS = Capability(
    name="youtube.comments",
    description=(
        "Fetch public YouTube comments and replies with authors, text, likes, "
        "and timestamps. Use video URLs."
    ),
    input_schema=CommentsInput,
    output_schema=CommentsOutput,
    executor=build_comments_executor(),
    billing_unit=BillingUnit.YOUTUBE_COMMENT,
    docs_url="/docs/connectors/native/youtube",
)

register_capability(YOUTUBE_COMMENTS)
