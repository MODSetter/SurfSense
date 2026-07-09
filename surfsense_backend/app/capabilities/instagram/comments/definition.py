"""``instagram.comments`` capability registration (billed per comment; see config
``INSTAGRAM_SCRAPE_MICROS_PER_COMMENT``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.instagram.comments.executor import build_comments_executor
from app.capabilities.instagram.comments.schemas import CommentsInput, CommentsOutput

INSTAGRAM_COMMENTS = Capability(
    name="instagram.comments",
    description=(
        "Fetch comments (and optionally replies) for Instagram post or reel URLs."
    ),
    input_schema=CommentsInput,
    output_schema=CommentsOutput,
    executor=build_comments_executor(),
    billing_unit=BillingUnit.INSTAGRAM_COMMENT,
    docs_url="/docs/connectors/native/instagram",
)

register_capability(INSTAGRAM_COMMENTS)
