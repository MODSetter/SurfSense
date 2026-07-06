"""``reddit.scrape`` capability registration (billed per item; see config
``REDDIT_SCRAPE_MICROS_PER_ITEM``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.reddit.scrape.executor import build_scrape_executor
from app.capabilities.reddit.scrape.schemas import ScrapeInput, ScrapeOutput

REDDIT_SCRAPE = Capability(
    name="reddit.scrape",
    description=(
        "Scrape public Reddit data. Give it Reddit URLs (post, subreddit, or "
        "user) and/or search terms, and it returns structured items — posts "
        "(title, body, score, comment count, subreddit, author), their comments, "
        "and community/user metadata. Use search_queries (optionally scoped to a "
        "community) to discover posts, or urls to pull a known post/subreddit/user."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.REDDIT_ITEM,
)

register_capability(REDDIT_SCRAPE)
