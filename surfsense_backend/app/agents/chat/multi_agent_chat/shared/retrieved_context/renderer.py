"""Render retrieved documents into the model-facing ``<retrieved_context>`` block.

Each passage is registered into the citation registry as it is rendered, so the
``[n]`` the model sees is the same label the server can later resolve back to a
chunk. ``[n]`` is the only citable integer per passage by design — nothing else
in a line is a number the model could echo by mistake.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)

from .models import RetrievedDocument, RetrievedPassage

_HEADER = (
    "These are excerpts from the user's knowledge base, selected for this query.\n"
    "A document is a full source (a file, a Slack thread, a Notion page); a chunk\n"
    "is one ordered fragment of it. Each document is tagged (partial) when only\n"
    "some of its chunks were retrieved or (complete) when all of them are shown\n"
    "here, so you know whether you have the whole source or only parts of it.\n"
    "Cite a chunk with [n]."
)


def render_retrieved_context(
    documents: list[RetrievedDocument],
    registry: CitationRegistry,
) -> str | None:
    """Render retrieved documents and register each passage for citation.

    Returns ``None`` when there is no passage to show so the caller can skip the
    block. Mutates ``registry`` (find-or-create), so a passage seen again in a
    later turn keeps its original ``[n]``.
    """
    blocks = [
        block
        for document in documents
        if (block := _render_document(document, registry)) is not None
    ]
    if not blocks:
        return None

    return "<retrieved_context>\n" + _HEADER + "\n" + "\n".join(blocks) + "\n</retrieved_context>"


def _render_document(
    document: RetrievedDocument,
    registry: CitationRegistry,
) -> str | None:
    """Render one document header and its passages; ``None`` if it has none."""
    if not document.passages:
        return None

    lines = [_render_header(document)]
    for passage in document.passages:
        lines.append(_render_passage(document, passage, registry))
    return "\n".join(lines)


def _render_header(document: RetrievedDocument) -> str:
    """``Document: "Title"  (source)  (partial|complete)``."""
    source = f"  ({document.source_label})" if document.source_label else ""
    completeness = "(complete)" if document.is_complete else "(partial)"
    return f'Document: "{_clean(document.title)}"{source}  {completeness}'


def _render_passage(
    document: RetrievedDocument,
    passage: RetrievedPassage,
    registry: CitationRegistry,
) -> str:
    """``  [n] <chunk content>`` with continuation lines indented under it."""
    n = registry.register(
        CitationSourceType.KB_CHUNK,
        {"document_id": passage.document_id, "chunk_id": passage.chunk_id},
        {"title": document.title, "source": document.source_label},
    )
    label = f"  [{n}] "
    body = passage.content.strip().replace("\n", "\n" + " " * len(label))
    return f"{label}{body}"


def _clean(text: str) -> str:
    """Collapse whitespace so a title stays on the header line."""
    return " ".join(text.split())


__all__ = ["render_retrieved_context"]
