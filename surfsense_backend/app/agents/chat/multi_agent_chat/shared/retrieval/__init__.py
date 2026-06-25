"""Knowledge-base retrieval: hybrid search rendered as citable evidence.

Public surface is the service (``search_knowledge_base_context``) and its input
value object (``SearchScope``); the rest are building blocks.
"""

from __future__ import annotations

from .models import ChunkHit, DocumentHit, SearchScope
from .service import build_context, search_knowledge_base_context

__all__ = [
    "ChunkHit",
    "DocumentHit",
    "SearchScope",
    "build_context",
    "search_knowledge_base_context",
]
