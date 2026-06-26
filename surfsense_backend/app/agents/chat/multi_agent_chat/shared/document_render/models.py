"""Inputs for rendering a citable document for the model.

A passage is one citable unit — what the model cites with ``[n]``. A document
groups the passages shown from one source. The same shapes feed every citable
surface: KB search excerpts, KB full reads, and web results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.agents.chat.multi_agent_chat.shared.citations import CitationSourceType

DocumentView = Literal["excerpt", "full"]
"""How much of the source is shown: a search slice, or the whole object."""


@dataclass(frozen=True)
class RenderablePassage:
    """One citable unit: what the model cites with ``[n]``.

    ``locator`` is the source-specific identity registered for this passage (a KB
    chunk's ``{document_id, chunk_id}``, a web result's ``{url}``). ``source_type``
    selects how that locator resolves to a frontend payload.
    """

    content: str
    locator: dict[str, Any]
    source_type: CitationSourceType = CitationSourceType.KB_CHUNK


@dataclass(frozen=True)
class RenderableDocument:
    """A source document and the passages to render from it, in order."""

    title: str
    source: str | None = None
    passages: list[RenderablePassage] = field(default_factory=list)


__all__ = ["DocumentView", "RenderableDocument", "RenderablePassage"]
