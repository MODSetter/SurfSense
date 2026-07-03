# ruff: noqa: N815 - public field names intentionally use camelCase
"""``web.crawl`` I/O contracts.

A Website Content Crawler-style surface: one verb that either scrapes the given
URLs (``maxCrawlDepth == 0``) or spiders their site (``maxCrawlDepth > 0``),
bounded by ``maxCrawlPages`` and kept on the seed's site.

Fields are trimmed to what the proprietary engine honors today. Knobs the engine
handles automatically (crawler type, proxy, dynamic-render waits) are
intentionally omitted, as are features we haven't built (URL globs, output
formats, click actions, PII handling).
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
    error: str | None = Field(
        default=None, description="Failure reason when status is not success."
    )


class CrawlOutput(BaseModel):
    items: list[CrawlItem] = Field(
        default_factory=list,
        description="One item per fetched page, in crawl (BFS) order.",
    )
    # Billing-only telemetry; excluded from the wire shape (mirrors web.scrape).
    captcha_attempts: int = Field(default=0, exclude=True)
    captcha_solved: int = Field(default=0, exclude=True)

    @property
    def billable_units(self) -> int:
        """Successful pages are the metered unit (03c)."""
        return sum(1 for item in self.items if item.status == "success")
