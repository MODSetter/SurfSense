"""Resolve ``@``-mentioned chat threads into read-only agent context.

Public surface for the referenced-chat feature: a user can mention
another conversation in the composer and the agent receives its
transcript as a ``<referenced_chat_context>`` block (read-only, never
merged into the active LangGraph state).

Split by responsibility:

* ``models`` — the data shapes shared across the slice.
* ``resolver`` — access-checked fetch of referenced threads + turns.
* ``transcript`` — render fetched turns into the XML block within a
  per-reference token budget.
"""

from __future__ import annotations

from .models import ReferencedChat
from .resolver import resolve_referenced_chats
from .transcript import render_referenced_chats_block

__all__ = [
    "ReferencedChat",
    "render_referenced_chats_block",
    "resolve_referenced_chats",
]
