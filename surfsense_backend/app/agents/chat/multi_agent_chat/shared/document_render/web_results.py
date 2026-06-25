"""Wrap live web-search results in a ``<web_results>`` block.

Each result renders through the shared ``render_document`` (excerpt view), so a
web result is cited with ``[n]`` exactly like a knowledge-base passage. Only the
container and header differ — they tell the model these came from the public web,
not the user's workspace.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry

from .document import render_document
from .models import RenderableDocument

_HEADER = (
    "These are live results from a public web search for this query. Each\n"
    "<document> below is one result in excerpt view; cite a result with its [n]\n"
    "after the statement it supports. Scrape the URL for full context before\n"
    "making a definitive claim from a snippet."
)


def render_web_results(
    documents: list[RenderableDocument],
    registry: CitationRegistry,
) -> str | None:
    """Render web results as excerpt blocks inside ``<web_results>``.

    Returns ``None`` when no result has content to show, so the caller can skip
    the block. Mutates ``registry`` (find-or-create), so a URL seen again keeps
    its original ``[n]``.
    """
    blocks = [
        block
        for document in documents
        if (
            block := render_document(document, view="excerpt", registry=registry)
        )
        is not None
    ]
    if not blocks:
        return None

    return (
        "<web_results>\n"
        + _HEADER
        + "\n"
        + "\n".join(blocks)
        + "\n</web_results>"
    )


__all__ = ["render_web_results"]
