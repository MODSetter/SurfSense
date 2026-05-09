"""Helpers for serving text and binary fixture file bodies."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_file_bytes(
    fixture: dict[str, Any], key: str | None, fixtures_dir: Path
) -> bytes | None:
    """Resolve a fake file body, preferring binary fixture files over text."""
    if not key:
        return None

    binary_path = fixture.get("_file_binary_paths", {}).get(key)
    if binary_path is not None:
        return (fixtures_dir / binary_path).read_bytes()

    content = fixture.get("_file_contents", {}).get(key)
    if content is None:
        return None
    return content.encode("utf-8")
