"""``web.discover`` I/O contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoverInput(BaseModel):
    query: str = Field(
        description="What to search the web for, phrased in natural language."
    )
    top_k: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results to return (1-50)."
    )


class DiscoverHit(BaseModel):
    url: str = Field(
        description="The result's page URL; pass it to web.scrape to read it."
    )
    title: str = Field(description="The result's page title.")
    snippet: str | None = Field(
        default=None, description="A short extract summarizing the page."
    )
    provider: str = Field(description="Which search engine returned this hit.")


class DiscoverOutput(BaseModel):
    hits: list[DiscoverHit] = Field(description="Ranked search results, best first.")
