# ruff: noqa: N815
"""Input/output models for the public Walmart scraper.

Two verbs share this module: ``walmart.scrape`` (products + listings) and
``walmart.reviews`` (deep paginated reviews). Walmart is a Next.js app that
ships its data as JSON in a ``<script id="__NEXT_DATA__">`` tag, so the parsers
read structured JSON rather than the rendered DOM — more robust against the
constant CSS/layout A/B testing on walmart.com.

Outputs use ``extra="allow"`` on purpose (same as the Amazon scraper): the wire
shape can grow without breaking existing consumers. Only the small, stable,
always-populated nested objects are typed; volatile sections stay loose.

Public, anonymous data only: there is no auth/login field. Deep review
pagination uses the public ``/reviews/product/{id}`` page, which robots.txt
permits (unlike ``/search``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Typed nested objects (the stable, always-populated ones).                   #
# --------------------------------------------------------------------------- #


class Price(BaseModel):
    """A monetary amount as Walmart renders it (``price``, ``listPrice``)."""

    model_config = ConfigDict(extra="allow")

    value: float | None = None
    currency: str | None = None


class Seller(BaseModel):
    """The offer seller. ``type`` distinguishes Walmart 1P from 3P marketplace."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    type: Literal["WALMART", "MARKETPLACE"] | None = None


# --------------------------------------------------------------------------- #
# Input surfaces.                                                             #
# --------------------------------------------------------------------------- #


class WalmartScrapeInput(BaseModel):
    """Full input surface for ``walmart.scrape``.

    ``startUrls`` mixes product (``/ip/``), search (``/search``), category
    (``/cp/``), and browse (``/browse/``) URLs; each is classified and dispatched
    by :mod:`.url_resolver`. ``extra="allow"`` keeps a verbatim payload valid.
    """

    model_config = ConfigDict(extra="allow")

    startUrls: list[str] = Field(min_length=1)
    maxItemsPerStartUrl: int | None = Field(default=None, ge=0)
    maxSearchPagesPerStartUrl: int = Field(default=25, ge=1)
    includeDetails: bool = True
    includeReviewsSample: bool = True
    country: str = "us"


class WalmartReviewsInput(BaseModel):
    """Full input surface for ``walmart.reviews`` (deep paginated reviews)."""

    model_config = ConfigDict(extra="allow")

    itemIds: list[str] = Field(min_length=1)
    maxReviews: int = Field(default=200, ge=1)
    sort: Literal["most-recent", "most-helpful", "rating-high", "rating-low"] = (
        "most-recent"
    )
    country: str = "us"


# --------------------------------------------------------------------------- #
# Output items.                                                               #
# --------------------------------------------------------------------------- #


class ProductItem(BaseModel):
    """``walmart.scrape`` output item (one per product / listing card).

    Unsourced fields default to ``None``/``[]``; ``extra="allow"`` keeps the
    contract open so later milestones add fields without breaking consumers.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Identity / core
    usItemId: str | None = None
    name: str | None = None
    brand: str | None = None
    url: str | None = None
    price: Price | None = None
    listPrice: Price | None = None
    currency: str | None = None
    availabilityStatus: str | None = None
    inStock: bool | None = None

    # Ratings / social
    stars: float | None = None
    reviewsCount: int | None = None

    # Commerce
    seller: Seller | None = None
    manufacturerName: str | None = None
    sponsored: bool | None = None

    # Content (detail pages only)
    shortDescription: str | None = None
    longDescription: str | None = None
    thumbnailImage: str | None = None
    images: list[str] = Field(default_factory=list)
    breadCrumbs: list[str] = Field(default_factory=list)
    category: str | None = None
    specifications: dict | None = None
    variants: list[dict] = Field(default_factory=list)
    fulfillment: dict | None = None

    # Embedded free review sample (detail pages only)
    reviewsSample: dict | None = None

    # Provenance / meta
    input: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat dict output shape (keeps extras)."""
        return self.model_dump(by_alias=True, exclude_none=False)


class ReviewItem(BaseModel):
    """``walmart.reviews`` output item (one per customer review)."""

    model_config = ConfigDict(extra="allow")

    reviewId: str | None = None
    rating: float | None = None
    title: str | None = None
    text: str | None = None
    submissionTime: str | None = None
    author: str | None = None
    verifiedPurchase: bool | None = None
    positiveFeedback: int | None = None
    negativeFeedback: int | None = None
    images: list[str] = Field(default_factory=list)
    syndicated: bool | None = None
    sellerResponse: str | None = None
    usItemId: str | None = None
    input: str | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


# --------------------------------------------------------------------------- #
# Error item (the failure model — pushed into the stream, not raised).        #
# --------------------------------------------------------------------------- #

ErrorCode = Literal[
    "invalid_url",
    "product_not_found",
    "no_results_found",
    "reviews_not_found",
]


class ErrorItem(BaseModel):
    """A per-input failure emitted into the dataset instead of a normal item.

    Consumers tell error items apart from products/reviews by the ``error`` key.
    """

    model_config = ConfigDict(extra="allow")

    error: ErrorCode
    errorDescription: str | None = None
    input: str | None = None
    url: str | None = None
