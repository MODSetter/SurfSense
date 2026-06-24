"""Retrieved knowledge-base evidence rendered as the ``<retrieved_context>`` block.

Turns retrieved chunks into the model-facing block and registers each passage
into the citation registry so ``[n]`` resolves back to a real chunk.
"""

from __future__ import annotations

from .models import RetrievedDocument, RetrievedPassage
from .renderer import render_retrieved_context

__all__ = [
    "RetrievedDocument",
    "RetrievedPassage",
    "render_retrieved_context",
]
