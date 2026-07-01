"""``web.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_SCRAPE_URLS = 20
"""Per-call batch cap: bounds a synchronous request's crawl fan-out (05)."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(
        min_length=1,
        max_length=MAX_SCRAPE_URLS,
        description=(
            "Full page URLs to fetch and read (1-20), each starting with "
            "http:// or https://. Pass the exact URLs you want the content of."
        ),
    )
    max_length: int = Field(
        default=50_000,
        description=(
            "Maximum characters of cleaned content returned per page; "
            "content longer than this is truncated."
        ),
    )

    @property
    def estimated_units(self) -> int:
        """Worst-case billable crawls for pre-flight: one per requested URL."""
        return len(self.urls)


class ScrapeRow(BaseModel):
    url: str = Field(description="The requested URL this result is for.")
    status: Literal["success", "empty", "failed"] = Field(
        description=(
            "'success' = content returned; 'empty' = page reached but no "
            "readable content; 'failed' = could not be fetched (see error)."
        )
    )
    content: str | None = Field(
        default=None, description="Cleaned, readable page text (present on success)."
    )
    metadata: dict[str, str] | None = Field(
        default=None, description="Page metadata such as title and description."
    )
    error: str | None = Field(
        default=None, description="Why the fetch failed (present on 'failed')."
    )


class ScrapeOutput(BaseModel):
    rows: list[ScrapeRow] = Field(
        description="One result per requested URL, in the same order."
    )

    @property
    def billable_units(self) -> int:
        """One billable unit per successful scrape."""
        return sum(1 for row in self.rows if row.status == "success")
