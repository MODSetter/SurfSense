"""Structured output schemas for memory extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
