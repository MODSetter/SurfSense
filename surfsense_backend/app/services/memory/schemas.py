"""Schemas for memory API responses and structured extraction."""

from __future__ import annotations

from pydantic import BaseModel


class MemoryLimits(BaseModel):
    """Canonical memory size limits exposed to clients."""

    soft: int
    hard: int


class MemoryRead(BaseModel):
    """Memory document payload returned by user and team memory APIs."""

    memory_md: str
    limits: MemoryLimits
