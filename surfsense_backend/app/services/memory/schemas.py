"""Schemas for memory API responses and structured extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemoryLimits(BaseModel):
    """Canonical memory size limits exposed to clients."""

    soft: int
    hard: int


class MemoryRead(BaseModel):
    """Memory document payload returned by user and team memory APIs."""

    memory_md: str
    limits: MemoryLimits


class MemoryExtractionDecision(BaseModel):
    """Structured extraction result; avoids string sentinel parsing."""

    action: Literal["no_update", "save"] = Field(
        description="Choose no_update when nothing durable should be saved; choose save otherwise."
    )
    reason: str | None = Field(
        default=None,
        description="Short reason for no_update, or brief summary of the memory update.",
    )
    updated_memory: str | None = Field(
        default=None,
        description="The full updated markdown memory document when action is save.",
    )
