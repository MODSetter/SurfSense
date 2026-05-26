"""``MetadataBlock`` — free-form metadata on a definition. Extra keys allowed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MetadataBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    tags: list[str] = Field(default_factory=list)
    created_from_nl: bool = Field(
        default=False, description="True when produced by the NL generator."
    )
