"""Map a registered citation to the frontend ``[citation:<payload>]`` payload.

The citation renderer understands a chunk id (``42``), a negative chunk id for
anonymous uploads (``-3``), and a URL. This is the seam that turns a server-side
source into one the renderer can resolve; it grows as more source kinds become
renderable. Kinds with no renderable form yet return ``None`` so the marker is
dropped rather than emitted broken.
"""

from __future__ import annotations

from .models import CitationEntry, CitationSourceType


def to_frontend_payload(entry: CitationEntry) -> str | None:
    """Inner payload for ``[citation:<payload>]``, or ``None`` if not renderable."""
    locator = entry.locator
    match entry.source_type:
        case CitationSourceType.KB_CHUNK | CitationSourceType.ANON_CHUNK:
            chunk_id = locator.get("chunk_id")
            return str(chunk_id) if chunk_id is not None else None
        case CitationSourceType.WEB_RESULT:
            url = locator.get("url")
            return url or None
        case _:
            return None


__all__ = ["to_frontend_payload"]
