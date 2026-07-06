"""``google_maps.reviews`` capability registration (billed per review; see
config ``GOOGLE_MAPS_MICROS_PER_REVIEW``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.google_maps.reviews.executor import build_reviews_executor
from app.capabilities.google_maps.reviews.schemas import ReviewsInput, ReviewsOutput

GOOGLE_MAPS_REVIEWS = Capability(
    name="google_maps.reviews",
    description=(
        "Fetch public reviews for one or more Google Maps places. Give it place "
        "URLs or place IDs; returns structured review items with author, text, "
        "star rating, like count, owner response, and timestamps. Use it to "
        "gauge sentiment or pull recent feedback on specific places."
    ),
    input_schema=ReviewsInput,
    output_schema=ReviewsOutput,
    executor=build_reviews_executor(),
    billing_unit=BillingUnit.GOOGLE_MAPS_REVIEW,
)

register_capability(GOOGLE_MAPS_REVIEWS)
