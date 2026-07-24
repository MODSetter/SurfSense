"""Knowledge-base retrieval: hybrid search rendered as citable evidence.

Public surface is ``build_context`` (rerank → adapt → render) and the
``SearchScope`` input value object; the rest are building blocks.
"""

from __future__ import annotations

from .models import ChunkHit, DocumentHit, SearchScope
from .service import build_context

__all__ = [
    "ChunkHit",
    "DocumentHit",
    "SearchScope",
    "build_context",
]
