"""The artifact contract every family speaks: grounding in, a Built out."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """One document handed to a generator as grounding."""

    document_id: int
    title: str
    content: str


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
