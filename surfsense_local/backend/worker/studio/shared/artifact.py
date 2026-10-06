"""The artifact contract every family speaks: grounding in, a Built out."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceImage:
    """A figure kept from a source, which a Word or PDF draft may place by name."""

    name: str
    caption: str | None
    path: Path


@dataclass(frozen=True)
class Source:
    """One document handed to a generator as grounding."""

    document_id: int
    title: str
    content: str
    # Filled only for the formats that place figures (Word and PDF).
    figures: tuple[SourceImage, ...] = ()


def fallback_title(user_prompt: str | None, sources: list[Source], label: str) -> str:
    """The name when the model gave none: the prompt, else the sources, else the format."""
    if user_prompt and user_prompt.strip():
        return user_prompt.strip()[:200]
    if not sources:
        return label
    more = len(sources) - 1
    return sources[0].title + (f" and {more} more" if more else "")


@dataclass
class Built:
    """A generator's output: the searchable body, and any blobs to store.

    `markdown` is always the indexed body (ADR-0003: the artifact is a Document).
    A file format also fills `primary`; `preview` is an optional rendered image.
    """

    title: str
    markdown: str
    primary: bytes | None = None
    primary_mime: str | None = None
    primary_filename: str | None = None
    preview: bytes | None = None
    preview_mime: str | None = None
    preview_filename: str | None = None
    # The source the next version is made from, for a format that keeps one.
    spec: dict[str, Any] | None = None
    # Kept in the version's metadata, such as how its workbook was recalculated.
    metadata: dict[str, Any] | None = None
