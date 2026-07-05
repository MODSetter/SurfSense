# ruff: noqa: N815 - public field names intentionally use camelCase
"""``web.crawl`` I/O contracts.

A Website Content Crawler-style surface: one verb that either scrapes the given
URLs (``maxCrawlDepth == 0``) or spiders their site (``maxCrawlDepth > 0``),
bounded by ``maxCrawlPages`` and kept on the seed's site.

Fields are trimmed to what the proprietary engine honors today. Knobs the engine
handles automatically (crawler type, proxy, dynamic-render waits) are
intentionally omitted, as are features we haven't built (output formats, click
actions, PII handling). Link following can be narrowed with include/exclude URL
regex patterns.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_START_URLS = 20
"""Per-call cap on seed URLs: bounds a synchronous request's fan-out (05)."""

MAX_CRAWL_DEPTH = 5
"""Deepest link distance a spider will follow from a start URL."""

MAX_CRAWL_PAGES = 200
"""Hard ceiling on pages fetched per call (protects the wallet and the run)."""


class CrawlInput(BaseModel):
    startUrls: list[str] = Field(
        min_length=1,
        max_length=MAX_START_URLS,
        description=(
            "Seed URLs to crawl. With maxCrawlDepth=0 only these are fetched; "
            "with a higher depth they are also the entry points for the spider."
        ),
    )
    maxCrawlDepth: int = Field(
        default=0,
        ge=0,
        le=MAX_CRAWL_DEPTH,
        description=(
            "How many link-hops to follow from each start URL. 0 = scrape only "
            "the start URLs (no spidering); 1 = also their linked pages; etc. "
            "The spider stays on the start URL's site."
        ),
    )
    maxCrawlPages: int = Field(
        default=10,
        ge=1,
        le=MAX_CRAWL_PAGES,
        description=(
            "Maximum number of pages to fetch in total (start URLs included). "
            "The crawl stops once this many pages have been fetched."
        ),
    )
    maxLength: int = Field(
        default=50_000,
        ge=1,
        description="Maximum characters of cleaned markdown kept per page (truncates beyond).",
    )
    includeUrlPatterns: list[str] = Field(
        default_factory=list,
        max_length=25,
        description=(
            "Regex patterns a discovered link must match to be followed "
            "(when maxCrawlDepth > 0). Empty = follow every same-site link. "
            "Ignored for the start URLs, which are always fetched."
        ),
    )
    excludeUrlPatterns: list[str] = Field(
        default_factory=list,
        max_length=25,
        description=(
            "Regex patterns that exclude a discovered link from being followed. "
            "Takes precedence over includeUrlPatterns."
        ),
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable pages for the pre-flight gate (03c)."""
        if self.maxCrawlDepth == 0:
            return len(self.startUrls)
        return self.maxCrawlPages


class CrawlMeta(BaseModel):
    loadedUrl: str = Field(description="The URL actually fetched for this page.")
    depth: int = Field(
        description="Link distance from a start URL (0 for a start URL itself)."
    )
    referrerUrl: str | None = Field(
        default=None,
        description="The page this URL was discovered on (null for start URLs).",
    )


class Link(BaseModel):
    url: str = Field(description="Absolute link target (or address for email/tel).")
    text: str = Field(
        default="",
        description="Anchor text — the label the page gives this link (e.g. a person's name on a LinkedIn link).",
    )
    context: str = Field(
        default="",
        description=(
            "For unlabeled social/email/tel links: surrounding text (e.g. the "
            "person card an icon link sits in). Empty when text says it all."
        ),
    )
    rel: str = Field(default="", description="The anchor's rel attribute, if any.")
    kind: Literal["internal", "external", "social", "email", "tel"] = Field(
        description=(
            "internal = same site; external = other site; social = known "
            "profile host (LinkedIn, X, GitHub, ...); email/tel = mailto:/tel: targets."
        ),
    )


class Contacts(BaseModel):
    emails: list[str] = Field(
        default_factory=list, description="Email addresses found on the page."
    )
    phones: list[str] = Field(
        default_factory=list, description="Phone numbers (from tel: links)."
    )
    socials: list[str] = Field(
        default_factory=list,
        description="Social/profile URLs (LinkedIn, X, GitHub, Instagram, etc.).",
    )


class ContactRef(BaseModel):
    """One site-wide contact value plus where it was found."""

    value: str = Field(description="The email address, phone number, or profile URL.")
    pages: list[str] = Field(
        description="First few page URLs this value was found on (crawl order)."
    )
    pageCount: int = Field(description="Total number of pages it appeared on.")
    siteWide: bool = Field(
        description=(
            "True when found on most fetched pages — i.e. header/footer "
            "boilerplate, so it belongs to the site itself (the company). "
            "False = page-local, e.g. one person's profile on a team page."
        ),
    )


class SiteContacts(BaseModel):
    emails: list[ContactRef] = Field(default_factory=list)
    phones: list[ContactRef] = Field(default_factory=list)
    socials: list[ContactRef] = Field(default_factory=list)


class CrawlItem(BaseModel):
    url: str = Field(description="The requested URL for this page.")
    status: Literal["success", "empty", "failed"] = Field(
        description="success = content returned; empty = fetched but no content; failed = could not fetch."
    )
    crawl: CrawlMeta | None = Field(
        default=None, description="Crawl provenance (loaded URL, depth, referrer)."
    )
    markdown: str | None = Field(
        default=None, description="Cleaned page content as markdown (null unless success)."
    )
    metadata: dict[str, str] | None = Field(
        default=None, description="Page metadata such as title and description."
    )
    contacts: Contacts | None = Field(
        default=None,
        description=(
            "Contact/social signals harvested from the page's raw HTML "
            "(footer/legal boilerplate that the markdown omits)."
        ),
    )
    links: list[Link] = Field(
        default_factory=list,
        description=(
            "Every link on the page with its anchor text and kind. The anchor "
            "text ties targets to entities (e.g. which person a LinkedIn URL "
            "belongs to) — use it instead of guessing from the URL."
        ),
    )
    error: str | None = Field(
        default=None, description="Failure reason when status is not success."
    )


class CrawlOutput(BaseModel):
    items: list[CrawlItem] = Field(
        default_factory=list,
        description="One item per fetched page, in crawl (BFS) order.",
    )
    contacts: SiteContacts = Field(
        default_factory=SiteContacts,
        description=(
            "Deduplicated union of every page's contact signals with provenance: "
            "each value lists the pages it was found on, and siteWide separates "
            "footer/header boilerplate (the company's own contacts) from "
            "page-local finds (e.g. individual people on a team page)."
        ),
    )
    # Billing-only telemetry; excluded from the wire shape (mirrors web.scrape).
    captcha_attempts: int = Field(default=0, exclude=True)
    captcha_solved: int = Field(default=0, exclude=True)

    @property
    def billable_units(self) -> int:
        """Successful pages are the metered unit (03c)."""
        return sum(1 for item in self.items if item.status == "success")
