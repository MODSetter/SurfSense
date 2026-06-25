"""Data shapes for the citation registry."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CitationSourceType(str, Enum):
    """Source kind of a citable unit; the value is the stable wire/dedup form."""

    KB_CHUNK = "kb_chunk"
    KB_DOCUMENT = "kb_document"
    CONNECTOR_ITEM = "connector_item"
    WEB_RESULT = "web_result"
    CHAT_TURN = "chat_turn"
    ANON_CHUNK = "anon_chunk"


class CitationEntry(BaseModel):
    """A registered unit: ``n`` (the label), ``locator`` (identity), ``display`` (UI only)."""

    n: int
    source_type: CitationSourceType
    locator: dict[str, Any]
    display: dict[str, Any] = Field(default_factory=dict)


__all__ = ["CitationEntry", "CitationSourceType"]
