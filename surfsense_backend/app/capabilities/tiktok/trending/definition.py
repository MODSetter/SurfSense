"""``tiktok.trending`` capability registration (billed per video on the shared
``TIKTOK_MICROS_PER_VIDEO`` meter)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.tiktok.trending.executor import build_trending_executor
from app.capabilities.tiktok.trending.schemas import TrendingInput, TrendingOutput

TIKTOK_TRENDING = Capability(
    name="tiktok.trending",
    description=(
        "Get the current trending TikTok videos from the Explore feed. No input "
        "needed beyond how many to return."
    ),
    input_schema=TrendingInput,
    output_schema=TrendingOutput,
    executor=build_trending_executor(),
    billing_unit=BillingUnit.TIKTOK_VIDEO,
    docs_url="/docs/connectors/native/tiktok",
)

register_capability(TIKTOK_TRENDING)
