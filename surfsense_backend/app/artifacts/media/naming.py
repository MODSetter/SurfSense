"""Sanitize primary filenames for media → Artifact cutover."""

from __future__ import annotations

import re

from app.knowledge_store.paths.naming import normalize_filename

_DOT_RUNS = re.compile(r"\.+")


def primary_filename(
    title: str | None,
    *,
    extension: str,
    fallback: str,
) -> str:
    """Build a path-safe ``{stem}.{extension}`` from a title.

    Uses the shared knowledge-store sanitizer, strips ``..`` / leading dots, then
    forces ``extension`` so a weird title cannot leave us with ``.md`` or an
    empty name that would break object-key construction.
    """
    ext = extension.lstrip(".").lower() or "bin"
    raw = (title or "").strip() or fallback
    sanitized = normalize_filename(f"{raw}.{ext}", fallback=f"{fallback}.{ext}")
    stem, _, got_ext = sanitized.rpartition(".")
    if not stem.strip() or got_ext.lower() != ext:
        stem = sanitized.rsplit(".", 1)[0] if "." in sanitized else sanitized
    stem = _DOT_RUNS.sub("_", stem).strip(" ._") or fallback
    return f"{stem}.{ext}"
