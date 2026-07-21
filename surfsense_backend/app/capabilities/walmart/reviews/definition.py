"""``walmart.reviews`` capability registration (billed per review; see config
``WALMART_MICROS_PER_REVIEW``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.walmart.reviews.executor import build_reviews_executor
from app.capabilities.walmart.reviews.schemas import ReviewsInput, ReviewsOutput

WALMART_REVIEWS = Capability(
    name="walmart.reviews",
    description=(
        "Fetch deep paginated public Walmart product reviews with ratings, text, "
        "authors, verified-purchase flags, images, and seller responses. Use "
        "product urls or item ids."
    ),
    input_schema=ReviewsInput,
    output_schema=ReviewsOutput,
    executor=build_reviews_executor(),
    billing_unit=BillingUnit.WALMART_REVIEW,
    docs_url="/docs/connectors/native/walmart",
)

register_capability(WALMART_REVIEWS)
