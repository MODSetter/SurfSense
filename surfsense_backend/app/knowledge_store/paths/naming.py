"""Sanitize text into a path-safe segment or filename; allocate fresh paths."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.knowledge_store.paths.store_path import StorePath, validate_segments

_INVALID_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|]+")
_WHITESPACE_RUN = re.compile(r"\s+")
_MAX_SEGMENT_LEN = 180
# Per-component filesystem limit is bytes, not characters (255 on ext4).
_MAX_SEGMENT_BYTES = 255


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    """Longest prefix whose UTF-8 encoding fits ``max_bytes``, cut on a char boundary."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[: max(max_bytes, 0)].decode("utf-8", "ignore")


def _clamp_segment_bytes(name: str, *, max_bytes: int = _MAX_SEGMENT_BYTES) -> str:
    """Clamp a filename to ``max_bytes``, keeping its extension."""
    if len(name.encode("utf-8")) <= max_bytes:
        return name
    stem, dot, ext = name.rpartition(".")
    if dot and stem:
        suffix = f".{ext}"
        budget = max_bytes - len(suffix.encode("utf-8"))
        return _truncate_to_bytes(stem, budget).rstrip() + suffix
    return _truncate_to_bytes(name, max_bytes).rstrip()


def safe_folder_segment(value: str, *, fallback: str = "folder") -> str:
    """Sanitize one folder name into a path-safe segment."""
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name or name in (".", ".."):
        return fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    return _truncate_to_bytes(name, _MAX_SEGMENT_BYTES).rstrip()


def normalize_filename(value: str, *, fallback: str = "untitled.md") -> str:
    """Sanitize text into a filename, defaulting a real extension to ``.md``."""
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        name = fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or not ext or len(ext) > 12 or " " in ext:
        name = f"{name}.md"
    return _clamp_segment_bytes(name)


def markdown_name_for_source(source_filename: str) -> str:
    """Tree name for an uploaded file: git holds the extracted ``.md``."""
    sanitized = normalize_filename(source_filename)
    stem = sanitized.rsplit(".", 1)[0]
    return f"{stem}.md" if stem else "untitled.md"


def allocate_path(
    *,
    name: str,
    folder_parts: Iterable[str],
    taken: set[str],
) -> StorePath:
    """Author a fresh path, breaking a collision with ``" (n)"``, never a doc id.

    ``taken`` is the set of occupied virtual paths; the chosen path is added to
    it so a batch stays collision-free.
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
        suffix = f" ({counter}){extension}"
        budget = _MAX_SEGMENT_BYTES - len(suffix.encode("utf-8"))
        disambiguated = _truncate_to_bytes(base, budget).rstrip() + suffix
        candidate = StorePath(validate_segments((*folders, disambiguated)))
        if candidate.virtual_path not in taken:
            taken.add(candidate.virtual_path)
            return candidate
        counter += 1
