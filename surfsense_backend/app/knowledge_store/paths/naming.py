"""Naming rules: how arbitrary text becomes a path-safe segment or filename.

The only place a fresh name is chosen. ``allocate_path`` is the authored-once
allocator; the sanitizers below back both it and the legacy renderers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.knowledge_store.paths.store_path import StorePath, validate_segments

_INVALID_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|]+")
_WHITESPACE_RUN = re.compile(r"\s+")
_MAX_SEGMENT_LEN = 180


def safe_folder_segment(value: str, *, fallback: str = "folder") -> str:
    """Sanitize one folder name into a path-safe segment."""
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        return fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    return name


def normalize_filename(value: str, *, fallback: str = "untitled.md") -> str:
    """Sanitize text into a filesystem-safe filename, defaulting to ``.md``.

    A name the author already gave an extension keeps it; a name without one
    gets ``.md`` because git holds markdown.
    """
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        name = fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or not ext or len(ext) > 12 or " " in ext:
        # No real extension (a lone trailing dot, or a "." inside prose): the
        # file is markdown, so say so rather than guess a type from the title.
        name = f"{name}.md"
    return name


def markdown_name_for_source(source_filename: str) -> str:
    """Filename an uploaded ``report.pdf`` gets in the tree: ``report.md``.

    Git holds the extracted markdown, not the source bytes, so the tree name
    matches the content. The original filename stays in ``document_files`` for
    the download path.
    """
    sanitized = normalize_filename(source_filename)
    stem = sanitized.rsplit(".", 1)[0]
    return f"{stem}.md" if stem else "untitled.md"


def allocate_path(
    *,
    name: str,
    folder_parts: Iterable[str],
    taken: set[str],
) -> StorePath:
    """Author a fresh path, resolving collisions once and deterministically.

    ``taken`` is the set of virtual paths already occupied (in the tree, or
    reserved earlier in the same batch). A collision appends ``" (2)"``,
    ``" (3)"``, ... before the extension — never a document id, which would tie
    the path to a row and reintroduce the churn the authored-once model removes.
    The chosen path is added to ``taken`` so the next call in the batch sees it.
    """
    folders = tuple(safe_folder_segment(p) for p in folder_parts if str(p).strip())
    filename = normalize_filename(name)
    candidate = StorePath(validate_segments((*folders, filename)))
    if candidate.virtual_path not in taken:
        taken.add(candidate.virtual_path)
        return candidate

    stem, dot, ext = filename.rpartition(".")
    base, extension = (stem, f".{ext}") if dot else (filename, "")
    counter = 2
    while True:
        disambiguated = f"{base} ({counter}){extension}"
        candidate = StorePath(validate_segments((*folders, disambiguated)))
        if candidate.virtual_path not in taken:
            taken.add(candidate.virtual_path)
            return candidate
        counter += 1
