# ruff: noqa: N815 - field names intentionally mirror the Apify camelCase spec
"""Apify-compatible input/output models for the Google Maps scraper.

The models mirror the public Apify "Google Maps Scraper" and "Google Maps
Reviews Scraper" actor specs so the endpoints can be drop-ins. The skeleton
accepts the full input surface; output fields the implementation does not
source yet are emitted as ``None``/``[]``/``{}`` so parity is additive.

Outputs use ``extra="allow"`` on purpose: it lets us grow the output shape
without breaking existing consumers, exactly like the YouTube scraper models.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SearchMatching = Literal["all", "only_includes", "only_exact"]
PlaceMinimumStars = Literal[
    "", "two", "twoAndHalf", "three", "threeAndHalf", "four", "fourAndHalf"
]
WebsiteFilter = Literal["allPlaces", "withWebsite", "withoutWebsite"]
ReviewsSort = Literal["newest", "mostRelevant", "highestRanking", "lowestRanking"]
ReviewsOrigin = Literal["all", "google"]
AllPlacesAction = Literal["", "all_places_no_search_ocr", "all_places_no_search_mouse"]


class StartUrl(BaseModel):
    """A single direct URL entry (Apify passes ``{"url": ...}`` objects)."""

    model_config = ConfigDict(extra="allow")

    url: str


class SocialMediaEnrichment(BaseModel):
    """Per-platform toggles for the social media profile enrichment add-on."""

    model_config = ConfigDict(extra="allow")

    facebooks: bool = False
    instagrams: bool = False
    youtubes: bool = False
    tiktoks: bool = False
    twitters: bool = False


class GoogleMapsScrapeInput(BaseModel):
    """Full Apify "Google Maps Scraper" input surface.

    Semantics follow Apify: ``maxCrawledPlacesPerSearch=None`` means "all
    places"; add-on toggles default off; ``maxReviews``/``maxImages``/
    ``maxQuestions`` of ``0`` mean "fetch none of that type".
    """

    model_config = ConfigDict(extra="allow")

    # Discovery
    searchStringsArray: list[str] = Field(default_factory=list)
    locationQuery: str | None = None
    startUrls: list[StartUrl] = Field(default_factory=list)
    placeIds: list[str] = Field(default_factory=list)
    allPlacesNoSearchAction: AllPlacesAction = ""

    # Caps / language
    maxCrawledPlacesPerSearch: int | None = Field(default=None, ge=1)
    language: str = "en"

    # Filters ($)
    categoryFilterWords: list[str] = Field(default_factory=list)
    searchMatching: SearchMatching = "all"
    placeMinimumStars: PlaceMinimumStars = ""
    website: WebsiteFilter = "allPlaces"
    skipClosedPlaces: bool = False

    # Place detail page ($) and its dependents
    scrapePlaceDetailPage: bool = False
    scrapeTableReservationProvider: bool = False
    scrapeOrderOnline: bool = False
    includeWebResults: bool = False
    scrapeDirectories: bool = False
    maxQuestions: int = Field(default=0, ge=0)

    # Enrichment add-ons ($)
    scrapeContacts: bool = False
    scrapeSocialMediaProfiles: SocialMediaEnrichment = Field(
        default_factory=SocialMediaEnrichment
    )
    maximumLeadsEnrichmentRecords: int = Field(default=0, ge=0)
    leadsEnrichmentDepartments: list[str] = Field(default_factory=list)
    verifyLeadsEnrichmentEmails: bool = False

    # Reviews ($)
    maxReviews: int = Field(default=0, ge=0)
    reviewsStartDate: str | None = None
    reviewsSort: ReviewsSort = "newest"
    reviewsFilterString: str = ""
    reviewsOrigin: ReviewsOrigin = "all"
    scrapeReviewsPersonalData: bool = True

    # Images ($)
    maxImages: int = Field(default=0, ge=0)
    scrapeImageAuthors: bool = False

    # Competitor analysis add-on ($)
    enableCompetitorAnalysis: bool = False
    maxCompetitorsToAnalyze: int = Field(default=30, ge=0, le=100)

    # Geolocation parameters (use either these or locationQuery, not both)
    countryCode: str | None = None
    city: str | None = None
    state: str | None = None
    county: str | None = None
    postalCode: str | None = None
    customGeolocation: dict[str, Any] | None = None


class Location(BaseModel):
    model_config = ConfigDict(extra="allow")

    lat: float | None = None
    lng: float | None = None


class ReviewsDistribution(BaseModel):
    model_config = ConfigDict(extra="allow")

    oneStar: int | None = None
    twoStar: int | None = None
    threeStar: int | None = None
    fourStar: int | None = None
    fiveStar: int | None = None


class OpeningHour(BaseModel):
    model_config = ConfigDict(extra="allow")

    day: str | None = None
    hours: str | None = None


class PeopleAlsoSearchItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str | None = None
    title: str | None = None
    reviewsCount: int | None = None
    totalScore: float | None = None


class ReviewsTag(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    count: int | None = None


class ImageItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    imageUrl: str | None = None
    authorName: str | None = None
    authorUrl: str | None = None
    uploadedAt: str | None = None


class ReviewFields(BaseModel):
    """Review-level fields shared by the nested place ``reviews[]`` items and
    the standalone Reviews Scraper output items."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    text: str | None = None
    textTranslated: str | None = None
    publishAt: str | None = None
    publishedAtDate: str | None = None
    likesCount: int | None = None
    reviewId: str | None = None
    reviewUrl: str | None = None
    reviewerId: str | None = None
    reviewerUrl: str | None = None
    reviewerPhotoUrl: str | None = None
    reviewerNumberOfReviews: int | None = None
    isLocalGuide: bool | None = None
    reviewOrigin: str | None = None
    stars: float | None = None
    rating: str | None = None
    responseFromOwnerDate: str | None = None
    responseFromOwnerText: str | None = None
    reviewImageUrls: list[str] = Field(default_factory=list)
    reviewContext: dict[str, Any] = Field(default_factory=dict)
    reviewDetailedRating: dict[str, Any] = Field(default_factory=dict)
    visitedIn: str | None = None
    originalLanguage: str | None = None
    translatedLanguage: str | None = None


class PlaceItem(BaseModel):
    """Apify "Google Maps Scraper" output item (one per place).

    Mirrors the actor's example JSON. Unsourced fields default to
    ``None``/``[]``/``{}``; ``extra="allow"`` keeps the contract open.
    """

    model_config = ConfigDict(extra="allow")

    # Provenance
    searchString: str | None = None
    rank: int | None = None
    searchPageUrl: str | None = None
    searchPageLoadedUrl: str | None = None
    isAdvertisement: bool = False

    # Identity
    title: str | None = None
    subTitle: str | None = None
    description: str | None = None
    price: str | None = None
    categoryName: str | None = None
    categories: list[str] = Field(default_factory=list)
    placeId: str | None = None
    fid: str | None = None
    cid: str | None = None
    kgmid: str | None = None

    # Address / location
    address: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    city: str | None = None
    postalCode: str | None = None
    state: str | None = None
    countryCode: str | None = None
    location: Location | None = None
    plusCode: str | None = None
    locatedIn: str | None = None
    parentPlaceUrl: str | None = None

    # Contact
    website: str | None = None
    phone: str | None = None
    phoneUnformatted: str | None = None
    menu: str | None = None
    servicesLink: str | None = None
    claimThisBusiness: bool | None = None

    # Ratings / status
    totalScore: float | None = None
    reviewsCount: int | None = None
    reviewsDistribution: ReviewsDistribution | None = None
    permanentlyClosed: bool = False
    temporarilyClosed: bool = False

    # Images
    imageUrl: str | None = None
    imagesCount: int | None = None
    imageCategories: list[str] = Field(default_factory=list)
    images: list[ImageItem] = Field(default_factory=list)
    imageUrls: list[str] = Field(default_factory=list)

    # Detail-page fields (populated only when scrapePlaceDetailPage)
    openingHours: list[OpeningHour] = Field(default_factory=list)
    peopleAlsoSearch: list[PeopleAlsoSearchItem] = Field(default_factory=list)
    placesTags: list[Any] = Field(default_factory=list)
    reviewsTags: list[ReviewsTag] = Field(default_factory=list)
    additionalInfo: dict[str, Any] | None = None
    questionsAndAnswers: list[Any] = Field(default_factory=list)
    updatesFromCustomers: Any | None = None
    ownerUpdates: list[Any] = Field(default_factory=list)
    webResults: list[Any] = Field(default_factory=list)
    tableReservationLinks: list[Any] = Field(default_factory=list)
    bookingLinks: list[Any] = Field(default_factory=list)
    reserveTableUrl: str | None = None
    googleFoodUrl: str | None = None
    gasPrices: list[Any] = Field(default_factory=list)
    restaurantData: dict[str, Any] = Field(default_factory=dict)
    userPlaceNote: str | None = None

    # Hotel fields
    hotelStars: str | None = None
    hotelDescription: str | None = None
    checkInDate: str | None = None
    checkOutDate: str | None = None
    similarHotelsNearby: Any | None = None
    hotelReviewSummary: Any | None = None
    hotelAds: list[Any] = Field(default_factory=list)

    # Reviews (populated only when maxReviews > 0)
    reviews: list[ReviewFields] = Field(default_factory=list)

    # Meta
    url: str | None = None
    scrapedAt: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat dict shape Apify emits (keeps extras)."""
        return self.model_dump(exclude_none=False)


class GoogleMapsReviewsInput(BaseModel):
    """Apify "Google Maps Reviews Scraper" input surface."""

    model_config = ConfigDict(extra="allow")

    startUrls: list[StartUrl] = Field(default_factory=list)
    placeIds: list[str] = Field(default_factory=list)
    maxReviews: int = Field(default=10_000_000, ge=1)
    reviewsSort: ReviewsSort = "newest"
    reviewsStartDate: str | None = None
    language: str = "en"
    reviewsOrigin: ReviewsOrigin = "all"
    personalData: bool = True


class ReviewItem(ReviewFields):
    """Apify "Google Maps Reviews Scraper" output item.

    One flat item per review: the review fields (inherited) merged with the
    place fields, per the actor's output schema.
    """

    # Place
    title: str | None = None
    placeId: str | None = None
    address: str | None = None
    location: Location | None = None
    categories: list[str] = Field(default_factory=list)
    isAdvertisement: bool = False
    categoryName: str | None = None
    totalScore: float | None = None
    permanentlyClosed: bool = False
    temporarilyClosed: bool = False
    reviewsCount: int | None = None
    url: str | None = None
    price: str | None = None
    cid: str | None = None
    fid: str | None = None
    imageUrl: str | None = None
    hotelStars: str | None = None
    kgmid: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    city: str | None = None
    countryCode: str | None = None
    postalCode: str | None = None
    state: str | None = None

    # Provenance / meta
    scrapedAt: str | None = None
    searchPageUrl: str | None = None
    searchString: str | None = None
    inputPlaceId: str | None = None
    inputStartUrl: str | None = None
    language: str | None = None
    rank: int | None = None

    def to_output(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
