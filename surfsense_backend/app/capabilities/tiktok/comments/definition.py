"""``tiktok.comments`` capability registration (billed per comment; see config
``TIKTOK_MICROS_PER_COMMENT``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.tiktok.comments.executor import build_comments_executor
from app.capabilities.tiktok.comments.schemas import CommentsInput, CommentsOutput

TIKTOK_COMMENTS = Capability(
    name="tiktok.comments",
    description=(
        "Scrape the public comments of TikTok videos. Provide video URLs; "
        "returns comment text, author, likes, and reply counts."
    ),
    input_schema=CommentsInput,
    output_schema=CommentsOutput,
    executor=build_comments_executor(),
    billing_unit=BillingUnit.TIKTOK_COMMENT,
    docs_url="/docs/connectors/native/tiktok",
)

register_capability(TIKTOK_COMMENTS)
