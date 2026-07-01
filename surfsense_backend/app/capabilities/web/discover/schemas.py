"""``web.discover`` I/O contracts."""

from __future__ import annotations

from pydantic import BaseModel


class DiscoverInput(BaseModel):
    query: str
    top_k: int = 10


class DiscoverHit(BaseModel):
    url: str
    title: str
    snippet: str | None = None
    provider: str


class DiscoverOutput(BaseModel):
    hits: list[DiscoverHit]
