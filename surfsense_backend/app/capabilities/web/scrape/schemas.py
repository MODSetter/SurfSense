"""``web.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_SCRAPE_URLS = 20
"""Per-call batch cap: bounds a synchronous request's crawl fan-out (05)."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=MAX_SCRAPE_URLS)
    max_length: int = 50_000

    @property
    def estimated_units(self) -> int:
        """Worst-case billable crawls for pre-flight: one per requested URL."""
        return len(self.urls)


class ScrapeRow(BaseModel):
    url: str
    status: Literal["success", "empty", "failed"]
    content: str | None = None
    metadata: dict[str, str] | None = None
    error: str | None = None


class ScrapeOutput(BaseModel):
    rows: list[ScrapeRow]

    @property
    def billable_units(self) -> int:
        """One billable unit per successful scrape."""
        return sum(1 for row in self.rows if row.status == "success")
