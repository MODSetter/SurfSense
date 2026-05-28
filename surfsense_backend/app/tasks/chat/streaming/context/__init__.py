"""Pre-agent context shaping: mentioned-doc rendering and todos extraction."""

from __future__ import annotations

from app.tasks.chat.streaming.context.deepagents_todos import (
    extract_todos_from_deepagents,
)
from app.tasks.chat.streaming.context.mentioned_docs import (
    format_mentioned_surfsense_docs_as_context,
)

__all__ = [
    "extract_todos_from_deepagents",
    "format_mentioned_surfsense_docs_as_context",
]
