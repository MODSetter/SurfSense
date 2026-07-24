"""``youtube.scrape`` capability registration (billed per video; see config
``YOUTUBE_MICROS_PER_VIDEO``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.youtube.scrape.executor import build_scrape_executor
from app.capabilities.youtube.scrape.schemas import ScrapeInput, ScrapeOutput

YOUTUBE_SCRAPE = Capability(
    name="youtube.scrape",
    description=(
        "Scrape public YouTube videos, channels, playlists, and subtitles. Use "
        "urls or search_queries."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.YOUTUBE_VIDEO,
    docs_url="/docs/connectors/native/youtube",
)

register_capability(YOUTUBE_SCRAPE)
