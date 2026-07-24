# ruff: noqa: N815 - field names intentionally mirror the Apify camelCase spec
"""Apify-compatible input/output models for the Google Search results scraper.

The models mirror the public Apify "Google Search Results Scraper" actor spec
so the endpoint can be a drop-in. The skeleton accepts the full input surface;
output fields the implementation does not source yet are emitted as
``None``/``[]``/``{}`` so parity is additive.

Excluded on purpose (Apify implements them by piping into *other* actors /
third-party data brokers, out of scope here): ``perplexitySearch``,
``chatGptSearch``, ``copilotSearch``, ``geminiSearch``, ``linkProspecting``,
and the business-leads enrichment trio (``maximumLeadsEnrichmentRecords``,
``leadsEnrichmentDepartments``, ``verifyLeadsEnrichmentEmails``). They are
still *accepted* via ``extra="allow"`` — a verbatim Apify payload validates —
but they are ignored, not modeled.

Outputs use ``extra="allow"`` on purpose: it lets us grow the output shape
without breaking existing consumers, exactly like the YouTube/Maps models.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Device = Literal["DESKTOP", "MOBILE"]


class AiOverviewAddon(BaseModel):
    """``aiOverview`` add-on toggle object (Apify nests it)."""

    model_config = ConfigDict(extra="allow")

    scrapeFullAiOverview: bool = False


class AiModeAddon(BaseModel):
    """``aiModeSearch`` add-on toggle object (Google AI Mode on google.com)."""

    model_config = ConfigDict(extra="allow")

    enableAiMode: bool = False


class GoogleSearchScrapeInput(BaseModel):
    """Full Apify "Google Search Results Scraper" input surface (minus the
    other-actor add-ons; see module docstring).

    Semantics follow Apify: ``queries`` is a newline-separated string mixing
    plain search terms and full Google Search URLs; ``maxPagesPerQuery=None``
    means one page; add-on toggles default off; ``saveHtmlToKeyValueStore``
    defaults **on** (matching the actor).
    """

    model_config = ConfigDict(extra="allow")

    # Discovery
    queries: str
    maxPagesPerQuery: int | None = Field(default=None, ge=1)

    # AI add-ons ($)
    aiOverview: AiOverviewAddon = Field(default_factory=AiOverviewAddon)
    aiModeSearch: AiModeAddon = Field(default_factory=AiModeAddon)

    # Paid results add-on ($)
    focusOnPaidAds: bool = False

    # Localization
    countryCode: str | None = None
    searchLanguage: str = ""
    languageCode: str = ""
    locationUule: str | None = None

    # Advanced search filters (composed into the query string)
    forceExactMatch: bool = False
    site: str | None = None
    relatedToSite: str | None = None
    wordsInTitle: list[str] = Field(default_factory=list, max_length=32)
    wordsInText: list[str] = Field(default_factory=list, max_length=32)
    wordsInUrl: list[str] = Field(default_factory=list, max_length=32)
    quickDateRange: str | None = None
    beforeDate: str | None = None
    afterDate: str | None = None
    fileTypes: list[str] = Field(default_factory=list, max_length=10)

    # Result shaping
    mobileResults: bool = False
    includeUnfilteredResults: bool = False
    saveHtml: bool = False
    saveHtmlToKeyValueStore: bool = True
    includeIcons: bool = False


class SearchQuery(BaseModel):
    """Provenance block stamped on every SERP item (``searchQuery``)."""

    model_config = ConfigDict(extra="allow")

    term: str | None = None
    url: str | None = None
    device: Device = "DESKTOP"
    page: int | None = None
    type: str = "SEARCH"
    domain: str | None = None
    countryCode: str | None = None
    languageCode: str | None = None
    locationUule: str | None = None


class RelatedQuery(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None


class SiteLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    description: str | None = None


class OrganicResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    displayedUrl: str | None = None
    description: str | None = None
    date: str | None = None
    emphasizedKeywords: list[str] = Field(default_factory=list)
    siteLinks: list[SiteLink] = Field(default_factory=list)
    productInfo: dict[str, Any] = Field(default_factory=dict)
    icon: str | None = None  # Base64 image data, only when includeIcons
    type: str = "organic"
    position: int | None = None


class PaidResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    displayedUrl: str | None = None
    description: str | None = None
    emphasizedKeywords: list[str] = Field(default_factory=list)
    siteLinks: list[SiteLink] = Field(default_factory=list)
    icon: str | None = None
    type: str = "paid"
    adPosition: int | None = None


class PaidProduct(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    displayedUrl: str | None = None
    description: str | None = None
    prices: list[str] = Field(default_factory=list)


class PeopleAlsoAskItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str | None = None
    answer: str | None = None
    url: str | None = None
    title: str | None = None
    date: str | None = None


class SuggestedResult(BaseModel):
    """A relatedQueries entry re-emitted in result shape (Apify synthesizes
    suggestedResults from the related-searches block, 1-based positions)."""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    type: str = "organic"
    position: int | None = None


class AiSource(BaseModel):
    """A page cited by an AI answer (AI Overview / AI Mode)."""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    url: str | None = None
    description: str | None = None
    imageUrl: str | None = None


class AiOverviewResult(BaseModel):
    """The AI Overview block that appears inline on some SERPs."""

    model_config = ConfigDict(extra="allow")

    content: str | None = None
    sources: list[AiSource] = Field(default_factory=list)


class AiModeResult(BaseModel):
    """One Google AI Mode answer (the ``aiModeResult`` add-on output)."""

    model_config = ConfigDict(extra="allow")

    engine: str = "AI Mode"
    provider: str = "Google"
    text: str | None = None
    sources: list[AiSource] = Field(default_factory=list)
    query: str | None = None
    kvsHtmlUrl: str | None = None
    url: str | None = None


class SerpItem(BaseModel):
    """Apify "Google Search Results Scraper" output item (one per SERP page).

    Mirrors the actor's example JSON. Unsourced fields default to
    ``None``/``[]``; ``extra="allow"`` keeps the contract open.
    """

    model_config = ConfigDict(extra="allow")

    searchQuery: SearchQuery = Field(default_factory=SearchQuery)
    resultsTotal: int | None = None

    organicResults: list[OrganicResult] = Field(default_factory=list)
    paidResults: list[PaidResult] = Field(default_factory=list)
    paidProducts: list[PaidProduct] = Field(default_factory=list)
    relatedQueries: list[RelatedQuery] = Field(default_factory=list)
    peopleAlsoAsk: list[PeopleAlsoAskItem] = Field(default_factory=list)
    suggestedResults: list[SuggestedResult] = Field(default_factory=list)

    # AI add-ons (populated only when the respective add-on is enabled /
    # the block appears on the page)
    aiOverview: AiOverviewResult | None = None
    aiModeResult: AiModeResult | None = None

    # HTML capture (saveHtml / saveHtmlToKeyValueStore)
    html: str | None = None
    htmlSnapshotUrl: str | None = None

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat dict shape Apify emits (keeps extras)."""
        return self.model_dump(exclude_none=False)
