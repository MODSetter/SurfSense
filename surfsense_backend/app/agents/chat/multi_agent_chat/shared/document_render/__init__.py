"""Render citable documents for the model: one shape for search, read, and web.

``render_document`` emits one ``<document title=… source=… view="excerpt|full">``
block whose passages carry server-assigned ``[n]`` labels. ``render_search_context``
wraps KB excerpt blocks in ``<retrieved_context>``; ``render_web_results`` wraps web
excerpt blocks in ``<web_results>``. Both cite with the same ``[n]`` spine.
"""

from __future__ import annotations

from .document import render_document
from .models import DocumentView, RenderableDocument, RenderablePassage
from .search_context import render_search_context
from .source_label import source_label
from .web_results import render_web_results

__all__ = [
    "DocumentView",
    "RenderableDocument",
    "RenderablePassage",
    "render_document",
    "render_search_context",
    "render_web_results",
    "source_label",
]
