"""Render citable documents for the model: one shape for search and read.

``render_document`` emits one ``<document title=… source=… view="excerpt|full">``
block whose passages carry server-assigned ``[n]`` labels. ``render_search_context``
wraps KB excerpt blocks in ``<retrieved_context>`` and cites with the ``[n]`` spine.
"""

from __future__ import annotations

from .document import render_document
from .models import DocumentView, RenderableDocument, RenderablePassage
from .search_context import render_search_context
from .source_label import source_label

__all__ = [
    "DocumentView",
    "RenderableDocument",
    "RenderablePassage",
    "render_document",
    "render_search_context",
    "source_label",
]
