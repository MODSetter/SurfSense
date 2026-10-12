# ruff: noqa: N815 - field names intentionally use the public camelCase API
"""Input/output models for the Indeed scraper.

Anonymous scraper: there is no auth field. Fields absent from a listing (full
description, benefits) stay ``None``/``[]`` until a detail fetch fills them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IndeedSort = Literal["relevance", "date"]
IndeedJobType = Literal[
    "fulltime",
    "parttime",
    "contract",
    "internship",
    "temporary",
    "permanent",
    "seasonal",
    "freelance",
]
IndeedLevel = Literal["entry_level", "mid_level", "senior_level"]
IndeedRemote = Literal["remote", "hybrid"]
SalaryPeriod = Literal["hour", "day", "week", "month", "year"]


class StartUrl(BaseModel):
    """A direct URL entry; extra keys ignored."""

    model_config = ConfigDict(extra="allow")

    url: str


class IndeedScrapeInput(BaseModel):
    """Indeed scraper input. Caps are collector policy, enforced by ``scrape_indeed``."""

    model_config = ConfigDict(extra="allow")

    # Discovery: direct URLs and/or search queries.
    startUrls: list[StartUrl] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)

    # Search parameters applied to ``queries``.
    country: str = "us"
    location: str | None = None
    radius: int | None = None
    jobType: IndeedJobType | None = None
    level: IndeedLevel | None = None
    remote: IndeedRemote | None = None
    fromDays: int | None = None
    sort: IndeedSort = "relevance"

    # Fetch each job's detail page for the full description.
    scrapeJobDetails: bool = False

    maxItems: int = Field(default=25, ge=0)
    maxItemsPerQuery: int = Field(default=25, ge=0)


class Salary(BaseModel):
    """Salary block; fields are ``None`` when Indeed omits pay."""

    model_config = ConfigDict(extra="allow")

    salaryText: str | None = None
    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str | None = None
    period: SalaryPeriod | None = None
    isEstimated: bool | None = None


class IndeedItem(BaseModel):
    """One job posting. ``extra="allow"`` keeps the contract additive."""

    model_config = ConfigDict(extra="allow")

    jobKey: str | None = None
    title: str | None = None
    jobUrl: str | None = None
    applyUrl: str | None = None

    company: str | None = None
    companyUrl: str | None = None
    companyRating: float | None = None
    companyReviewCount: int | None = None

    formattedLocation: str | None = None
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None
    isRemote: bool | None = None
    remoteType: str | None = None

    jobTypes: list[str] = Field(default_factory=list)
    salary: Salary = Field(default_factory=Salary)
    benefits: list[str] = Field(default_factory=list)

    descriptionText: str | None = None
    descriptionHtml: str | None = None

    sponsored: bool | None = None
    isNew: bool | None = None
    urgentlyHiring: bool | None = None
    expired: bool | None = None
    indeedApplyEnabled: bool | None = None

    age: str | None = None
    datePublished: str | None = None
    createdAt: str | None = None
    scrapedAt: str | None = None

    source: str = "indeed"

    def to_output(self) -> dict[str, Any]:
        """Serialize to the flat output dict, keeping extras."""
        return self.model_dump(exclude_none=False)
