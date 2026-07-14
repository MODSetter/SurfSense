"""``instagram.details`` capability registration (billed per item; see config
``INSTAGRAM_SCRAPE_MICROS_PER_ITEM``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.instagram.details.executor import build_details_executor
from app.capabilities.instagram.details.schemas import DetailsInput, DetailsOutput

INSTAGRAM_DETAILS = Capability(
    name="instagram.details",
    description=(
        "Fetch Instagram profile, hashtag, or place metadata by URL or discovery "
        "search. Each item carries a detailKind discriminator."
    ),
    input_schema=DetailsInput,
    output_schema=DetailsOutput,
    executor=build_details_executor(),
    billing_unit=BillingUnit.INSTAGRAM_ITEM,
    docs_url="/docs/connectors/native/instagram",
)

register_capability(INSTAGRAM_DETAILS)
