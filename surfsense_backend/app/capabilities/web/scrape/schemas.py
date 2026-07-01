"""``web.scrape`` I/O contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ScrapeInput(BaseModel):
    urls: list[str]
    max_length: int = 50_000


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
