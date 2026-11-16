# ruff: noqa: N815
"""Input/output models for the Amazon Product Scraper.

The skeleton accepts the full input surface; output fields the implementation
does not source yet are emitted as ``None``/``[]`` so parity is additive —
exactly like the YouTube / Maps / Google Search models.

Outputs use ``extra="allow"`` on purpose: it lets the output shape grow without
breaking existing consumers. Only a small set of stable, always-populated nested
objects (``price``, ``starsBreakdown``, ``seller``, ``visitStoreLink``) are
typed; the sprawling, layout-volatile sections (A+ content, brand story,
attribute tables, offers, on-page reviews, ...) stay loose ``dict``/``list`` and
lean on ``extra="allow"`` rather than pinning a shape the parsers haven't
verified against live HTML yet.

Public, anonymous data only: there is no auth/login field on the input surface.
Deep review pagination is login-gated on today's Amazon and is out of scope; the
on-page ``productPageReviews`` are the only reviews modeled here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Typed nested objects (the stable, always-populated ones).                   #
# --------------------------------------------------------------------------- #


class Price(BaseModel):
    """A monetary amount as Amazon renders it (``price``, ``listPrice``,
    ``shippingPrice``, and the ``min``/``max`` of ``priceRange``)."""

    model_config = ConfigDict(extra="allow")

    value: float | None = None
    currency: str | None = None


class StarsBreakdown(BaseModel):
    """Per-star rating distribution (fractions summing to ~1.0).

    Amazon's keys start with a digit (``5star`` ... ``1star``), which is not a
    valid Python identifier, so each field is aliased. ``populate_by_name`` lets
    tests construct it either way; ``to_output`` serializes ``by_alias`` so the
    wire shape retains the digit-prefixed keys.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    five_star: float | None = Field(default=None, alias="5star")
    four_star: float | None = Field(default=None, alias="4star")
    three_star: float | None = Field(default=None, alias="3star")
    two_star: float | None = Field(default=None, alias="2star")
    one_star: float | None = Field(default=None, alias="1star")


class Seller(BaseModel):
    """The featured-offer seller stamped on the product item."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    url: str | None = None
    reviewsCount: int | None = None
    averageRating: float | None = None


class VisitStoreLink(BaseModel):
    """The brand-store link (``visitStoreLink``)."""

    model_config = ConfigDict(extra="allow")

    text: str | None = None
    url: str | None = None


# --------------------------------------------------------------------------- #
# Input surface.                                                              #
# --------------------------------------------------------------------------- #


class AmazonScrapeInput(BaseModel):
    """Full input surface for the Amazon Product Scraper.

    ``categoryOrProductUrls`` mixes category/search, product, bestsellers, and
    shortened URLs; ``proxyCountry`` defaults to ``AUTO_SELECT_PROXY_COUNTRY``
    (derived from each URL's domain); ``scrapeProductDetails`` defaults on (deep
    scrape). ``extra="allow"`` keeps a verbatim payload valid even for add-ons
    this scraper does not model.
    """

    model_config = ConfigDict(extra="allow")

    # Discovery (required)
    categoryOrProductUrls: list[dict] = Field(min_length=1)

    # Result caps
    maxItemsPerStartUrl: int | None = Field(default=None, ge=0)
    maxSearchPagesPerStartUrl: int = Field(default=9999, ge=1)
    maxProductVariantsAsSeparateResults: int = Field(default=0, ge=0)
    maxOffers: int = Field(default=0, ge=0)

    # Localization
    language: str | None = None
    proxyCountry: str = "AUTO_SELECT_PROXY_COUNTRY"
    countryCode: str | None = None
    zipCode: str | None = None
    locationDeliverableRoutes: list[str] | None = Field(
        default_factory=lambda: ["PRODUCT", "SEARCH", "OFFERS"]
    )

    # Feature toggles
    scrapeSellers: bool = False
    useCaptchaSolver: bool = False
    scrapeProductVariantPrices: bool = False
    scrapeProductDetails: bool | None = True


# --------------------------------------------------------------------------- #
# Output item.                                                                #
# --------------------------------------------------------------------------- #


class ProductItem(BaseModel):
    """Amazon Product Scraper output item (one per product).

    Unsourced fields default to ``None``/``[]``; ``extra="allow"`` keeps the
    contract open so later milestones add fields without breaking consumers.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Identity / core
    title: str | None = None
    url: str | None = None
    asin: str | None = None
    originalAsin: str | None = None
    brand: str | None = None
    author: str | None = None
    price: Price | None = None
    listPrice: Price | None = None
    shippingPrice: Price | None = None
    inStock: bool | None = None
    inStockText: str | None = None
    delivery: str | None = None
    fastestDelivery: str | None = None
    condition: str | None = None

    # Ratings / social
    stars: float | None = None
    starsBreakdown: StarsBreakdown | None = None
    reviewsCount: int | None = None
    answeredQuestions: int | None = None
    aiReviewsSummary: dict | None = None
    monthlyPurchaseVolume: str | None = None

    # Content
    breadCrumbs: str | None = None
    description: str | None = None
    features: list[str] = Field(default_factory=list)
    sustainabilityFeatures: list[dict] = Field(default_factory=list)
    videosCount: int | None = None
    visitStoreLink: VisitStoreLink | None = None
    thumbnailImage: str | None = None
    galleryThumbnails: list[str] = Field(default_factory=list)
    highResolutionImages: list[str] = Field(default_factory=list)
    importantInformation: dict | None = None
    bookDescription: str | None = None
    aPlusContent: dict | None = None
    brandStory: dict | None = None
    productComparison: dict | None = None

    # Commerce
    returnPolicy: str | None = None
    support: str | None = None
    priceRange: dict | None = None
    variantAsins: list[str] = Field(default_factory=list)
    variantDetails: list[dict] = Field(default_factory=list)
    variantAttributes: list[dict] = Field(default_factory=list)
    attributes: list[dict] = Field(default_factory=list)
    attributesMapped: dict | None = None
    productOverview: list[dict] = Field(default_factory=list)
    manufacturerAttributes: list[dict] = Field(default_factory=list)
    seller: Seller | None = None
    bestsellerRanks: list[dict] = Field(default_factory=list)
    isAmazonChoice: bool | None = None
    amazonChoiceText: str | None = None
    offers: list[dict] = Field(default_factory=list)

    # Reviews (public, on-page only)
    reviewsLink: str | None = None
    hasReviews: bool | None = None
    productPageReviews: list[dict] = Field(default_factory=list)
    productPageReviewsFromOtherCountries: list[dict] = Field(default_factory=list)

    # Provenance / meta
    locationText: str | None = None
    unNormalizedProductUrl: str | None = None
    loadedCountryCode: str | None = None
    categoryPageData: dict | None = None
    bestsellerPageData: dict | None = None
    input: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat dict output shape (keeps extras, aliases).

        ``by_alias`` restores digit-prefixed keys like ``starsBreakdown.5star``;
        ``exclude_none=False`` keeps unsourced keys present so consumers never
        break on a missing field.
        """
        return self.model_dump(by_alias=True, exclude_none=False)


# --------------------------------------------------------------------------- #
# Error item (the failure model — pushed into the stream, not raised).        #
# --------------------------------------------------------------------------- #

ErrorCode = Literal[
    "invalid_url",
    "invalid_input",
    "product_not_found",
    "shortened_url_invalid",
    "bestsellers_category_not_found",
    "no_results_found",
]


class ErrorItem(BaseModel):
    """A per-input failure emitted into the dataset instead of a normal item.

    Consumers tell error items apart from products by the presence of ``error``.
    ``invalid_input`` additionally terminates the run (enforced in later
    milestones); all other codes are per-input and non-fatal.
    """

    model_config = ConfigDict(extra="allow")

    error: ErrorCode
    errorDescription: str | None = None
    input: str | None = None
    url: str | None = None
