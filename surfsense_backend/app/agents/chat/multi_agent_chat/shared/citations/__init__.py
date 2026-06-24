"""Citation registry: maps model-facing ``[n]`` labels to real sources.

Server-side only; the model sees only the bare ``[n]``.
"""

from __future__ import annotations

from .models import CitationEntry, CitationSourceType
from .registry import CitationRegistry, make_key

__all__ = [
    "CitationEntry",
    "CitationRegistry",
    "CitationSourceType",
    "make_key",
]
