"""``youtube.scrape`` capability registration (free — see 04-capabilities open item)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.youtube.scrape.executor import build_scrape_executor
from app.capabilities.youtube.scrape.schemas import ScrapeInput, ScrapeOutput

YOUTUBE_SCRAPE = Capability(
    name="youtube.scrape",
    description=(
        "Scrape public YouTube data. Give it YouTube URLs (video, channel, "
        "playlist, shorts, or hashtag) and/or search queries, and it returns "
        "structured video items — title, views, likes, publish date, channel "
        "info, description, and optionally subtitles. Use search_queries to "
        "discover videos, or urls to pull a known video/channel/playlist."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=None,
)

register_capability(YOUTUBE_SCRAPE)
