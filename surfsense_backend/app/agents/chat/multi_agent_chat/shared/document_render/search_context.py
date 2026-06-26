"""Wrap search excerpts in the ``<retrieved_context>`` block.

Each document renders through the shared ``render_document``; this module adds the
container and the one-time header that teaches the model how to read and cite.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry

from .document import render_document
from .models import RenderableDocument

_HEADER = (
    "These are excerpts from the user's knowledge base, selected for this query.\n"
    "A document is a full source (a file, a Slack thread, a Notion page); each\n"
    "<document> below is in excerpt view, so you are seeing only the chunks that\n"
    "matched this query, not the whole source. Cite a chunk with its [n]. Read the\n"
    "document for full context before claiming it only says X."
)


def render_search_context(
    documents: list[RenderableDocument],
    registry: CitationRegistry,
) -> str | None:
    """Render retrieved documents as excerpt blocks inside ``<retrieved_context>``.

    Returns ``None`` when no document has a passage to show, so the caller can skip
    the block. Mutates ``registry`` (find-or-create), so a passage seen again in a
    later turn keeps its original ``[n]``.
    """
    blocks = [
        block
        for document in documents
        if (block := render_document(document, view="excerpt", registry=registry))
        is not None
    ]
    if not blocks:
        return None

    return (
        "<retrieved_context>\n"
        + _HEADER
        + "\n"
        + "\n".join(blocks)
        + "\n</retrieved_context>"
    )


__all__ = ["render_search_context"]
