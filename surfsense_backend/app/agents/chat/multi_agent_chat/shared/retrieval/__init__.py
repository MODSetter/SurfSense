"""Knowledge-base retrieval: hybrid search rendered as citable evidence.

Public surface is ``build_context`` (rerank → adapt → render) and the
``SearchScope`` input value object; the rest are building blocks.
"""

from __future__ import annotations

from .models import ArtifactHit, ChunkHit, DocumentHit, KnowledgeHit, SearchScope
from .service import build_context

__all__ = [
    "ArtifactHit",
    "ChunkHit",
    "DocumentHit",
    "KnowledgeHit",
    "SearchScope",
    "build_context",
]
