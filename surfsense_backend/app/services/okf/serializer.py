"""Serialize SurfSense knowledge into Open Knowledge Format (OKF v0.1).

Pure functions with no HTTP / MCP / framework dependencies: given a
:class:`~app.db.Document` (and, for listings, its neighbours) they return
OKF-conformant markdown. Every consumer (ZIP export, REST, MCP, agents) calls
these rather than re-implementing frontmatter.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from app.db import Document
from app.services.okf.type_mapping import okf_resource, okf_type

# Reserved OKF filenames; never used for concept documents.
INDEX_FILENAME = "index.md"
LOG_FILENAME = "log.md"

_FRONTMATTER_DELIMITER = "---"


def _tags_from_metadata(metadata: dict[str, Any] | None) -> list[str] | None:
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("tags")
    if isinstance(raw, list):
        tags = [str(t).strip() for t in raw if str(t).strip()]
        return tags or None
    return None


def _timestamp(document: Document) -> str | None:
    when = document.updated_at or document.created_at
    if when is None:
        return None
    # ISO 8601, matching Google's sample bundles (e.g. 2026-05-28T22:49:59+00:00).
    return when.isoformat()


def build_frontmatter(document: Document) -> dict[str, Any]:
    """Build the ordered OKF frontmatter mapping for a document.

    Only ``type`` is required; recommended keys are included only when we have a
    value. Insertion order is preserved in the emitted YAML.
    """
    metadata = document.document_metadata if isinstance(document.document_metadata, dict) else {}

    frontmatter: dict[str, Any] = {"type": okf_type(document.document_type)}

    resource = okf_resource(document.document_type, metadata)
    if resource:
        frontmatter["resource"] = resource

    title = (document.title or "").strip()
    if title:
        frontmatter["title"] = title

    description = metadata.get("description")
    if isinstance(description, str) and description.strip():
        frontmatter["description"] = description.strip()

    tags = _tags_from_metadata(metadata)
    if tags:
        frontmatter["tags"] = tags

    timestamp = _timestamp(document)
    if timestamp:
        frontmatter["timestamp"] = timestamp

    return frontmatter


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Render a frontmatter mapping as a YAML block delimited by ``---``."""
    body = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return f"{_FRONTMATTER_DELIMITER}\n{body}{_FRONTMATTER_DELIMITER}\n"


def document_to_concept(document: Document, *, body: str) -> str:
    """Serialize a document as an OKF concept: frontmatter + ``body``.

    ``body`` is caller-resolved markdown, keeping this a pure formatting step.
    """
    frontmatter = render_frontmatter(build_frontmatter(document))
    body_text = (body or "").strip("\n")
    return f"{frontmatter}\n{body_text}\n"


@dataclass(frozen=True)
class ConceptRef:
    """One concept entry for an ``index.md`` listing."""

    title: str
    filename: str  # relative to the directory, e.g. "orders.md"
    type: str  # OKF type, used as the grouping heading
    description: str | None = None


@dataclass(frozen=True)
class SubdirRef:
    """One subdirectory entry for an ``index.md`` listing."""

    name: str  # directory name, e.g. "tables"
    description: str | None = None


@dataclass(frozen=True)
class LogEntry:
    """One line of an OKF ``log.md``: a concept and when it last changed."""

    title: str
    timestamp: str | None = None  # ISO-8601, or None when unknown


def folder_to_log(entries: list[LogEntry]) -> str:
    """Build a minimal OKF ``log.md`` body for one directory.

    Lists each concept newest-first with the time it last changed (from a
    document's ``updated_at``/``created_at``); undated entries sort last. Returns
    an empty string when there is nothing to log.

    ponytail: this is a last-touched summary, not a per-field change history. A
    fuller changelog would read ``DocumentVersion`` rows; upgrade there if
    consumers ever need diffs rather than "what changed and when".
    """
    if not entries:
        return ""
    ordered = sorted(
        entries,
        key=lambda e: (e.timestamp is not None, e.timestamp or "", e.title),
        reverse=True,
    )
    lines = ["# Change Log", ""]
    for entry in ordered:
        when = f" - {entry.timestamp}" if entry.timestamp else ""
        lines.append(f"* {entry.title}{when}")
    return "\n".join(lines) + "\n"


def _index_bullet(title: str, link: str, description: str | None) -> str:
    bullet = f"* [{title}]({link})"
    if description:
        # Keep index descriptions to a single line.
        bullet += f" - {' '.join(description.split())}"
    return bullet


def folder_to_index(
    *,
    concepts: list[ConceptRef] | None = None,
    subdirectories: list[SubdirRef] | None = None,
) -> str:
    """Build an OKF ``index.md`` body (no frontmatter) for one directory.

    Subdirectories are listed under a ``# Subdirectories`` heading and concepts
    are grouped under their ``type`` heading, mirroring Google's sample bundles.
    Returns an empty string when there is nothing to list.
    """
    concepts = concepts or []
    subdirectories = subdirectories or []
    sections: list[str] = []

    if subdirectories:
        lines = ["# Subdirectories", ""]
        for sub in sorted(subdirectories, key=lambda s: s.name.lower()):
            lines.append(
                _index_bullet(sub.name, f"{sub.name}/{INDEX_FILENAME}", sub.description)
            )
        sections.append("\n".join(lines))

    by_type: dict[str, list[ConceptRef]] = {}
    for concept in concepts:
        by_type.setdefault(concept.type, []).append(concept)
    for type_heading in sorted(by_type):
        lines = [f"# {type_heading}", ""]
        for concept in sorted(by_type[type_heading], key=lambda c: c.title.lower()):
            lines.append(
                _index_bullet(concept.title, concept.filename, concept.description)
            )
        sections.append("\n".join(lines))

    return ("\n\n".join(sections) + "\n") if sections else ""
