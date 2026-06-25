"""Citation registry: maps model-facing ``[n]`` labels to real sources.

Server-side only; the model sees only the bare ``[n]``.
"""

from __future__ import annotations

from .markers import to_frontend_payload
from .models import CitationEntry, CitationSourceType
from .normalizer import normalize_citations
from .registry import CitationRegistry, make_key

__all__ = [
    "CitationEntry",
    "CitationRegistry",
    "CitationSourceType",
    "make_key",
    "normalize_citations",
    "to_frontend_payload",
]
