from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """One document handed to a builder as grounding."""

    document_id: int
    title: str
    content: str


@dataclass
class Built:
    """A builder's output: the searchable body, and any blobs to store.

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


@dataclass(frozen=True)
class Builder:
    """A format: how to prompt the model, and how to render its answer.

    A new format is one module and one line in the registry — persistence and
    the routes stay format-blind.
    """

    key: str
    prompt: Callable[[list[Source], str | None], str]
    build: Callable[[str, list[Source]], Built]
