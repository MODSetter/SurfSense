"""Deterministic policies for stored artifact-generation source files."""

from __future__ import annotations

from pathlib import PurePosixPath
from types import MappingProxyType

SOURCE_MIME_TYPES = MappingProxyType(
    {
        ".html": "text/html",
        ".js": "text/javascript",
        ".py": "text/x-python",
    }
)


def validate_source_file(path: str, data: bytes) -> str:
    """Validate executable source as UTF-8 text and return its canonical MIME."""
    suffix = PurePosixPath(path).suffix.lower()
    try:
        mime_type = SOURCE_MIME_TYPES[suffix]
    except KeyError:
        raise ValueError(
            f"Unsupported artifact source type: {suffix or 'file without an extension'}"
        ) from None

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Artifact source must be valid UTF-8 text") from None
    if "\x00" in text:
        raise ValueError("Artifact source must not contain NUL bytes")
    return mime_type
