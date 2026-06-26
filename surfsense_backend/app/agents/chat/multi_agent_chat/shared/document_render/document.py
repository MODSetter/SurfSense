"""Render one citable document as a ``<document>`` block.

Every citable surface (KB search excerpts, KB full reads, web results) uses the
same block; ``view`` and the passages shown are what differ. Each passage is
registered for citation as it renders, so its ``[n]`` resolves back to its source
later.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry

from .models import DocumentView, RenderableDocument, RenderablePassage


def render_document(
    document: RenderableDocument,
    *,
    view: DocumentView,
    registry: CitationRegistry,
) -> str | None:
    """Render one ``<document>`` block, registering each passage for citation.

    Returns ``None`` when the document has no passage to show. Mutates ``registry``
    (find-or-create).
    """
    if not document.passages:
        return None

    lines = [_open_tag(document, view)]
    for passage in document.passages:
        lines.append(_render_passage(document, passage, registry))
    lines.append("</document>")
    return "\n".join(lines)


def _open_tag(document: RenderableDocument, view: DocumentView) -> str:
    attrs = [f'title="{_attr(document.title)}"']
    if document.source:
        attrs.append(f'source="{_attr(document.source)}"')
    attrs.append(f'view="{view}"')
    return f"<document {' '.join(attrs)}>"


def _render_passage(
    document: RenderableDocument,
    passage: RenderablePassage,
    registry: CitationRegistry,
) -> str:
    n = registry.register(
        passage.source_type,
        passage.locator,
        {"title": document.title, "source": document.source},
    )
    label = f"  [{n}] "
    body = passage.content.strip().replace("\n", "\n" + " " * len(label))
    return f"{label}{body}"


def _attr(value: str) -> str:
    collapsed = " ".join(str(value).split())
    return (
        collapsed.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = ["render_document"]
