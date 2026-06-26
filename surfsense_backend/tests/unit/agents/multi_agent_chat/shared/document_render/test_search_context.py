"""Tests for the ``<retrieved_context>`` wrapper around excerpt documents."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    render_search_context,
)

pytestmark = pytest.mark.unit


def _document(
    document_id: int,
    title: str,
    chunk_ids: list[int],
    *,
    source: str | None = None,
) -> RenderableDocument:
    return RenderableDocument(
        title=title,
        source=source,
        passages=[
            RenderablePassage(
                content=f"text {cid}",
                locator={"document_id": document_id, "chunk_id": cid},
            )
            for cid in chunk_ids
        ],
    )


def test_returns_none_when_nothing_to_show() -> None:
    registry = CitationRegistry()

    assert render_search_context([], registry) is None
    assert render_search_context([_document(1, "Empty", [])], registry) is None


def test_assigns_monotonic_labels_across_documents() -> None:
    registry = CitationRegistry()

    block = render_search_context(
        [
            _document(1, "Q3 Launch Notes", [880, 881], source="Slack"),
            _document(2, "Timeline", [12], source="Notion"),
        ],
        registry,
    )

    assert block is not None
    assert "[1] text 880" in block
    assert "[2] text 881" in block
    assert "[3] text 12" in block


def test_wraps_in_retrieved_context_and_teaches_excerpt_and_citation() -> None:
    registry = CitationRegistry()

    block = render_search_context([_document(1, "Doc", [1])], registry)

    assert block is not None
    assert block.startswith("<retrieved_context>")
    assert block.endswith("</retrieved_context>")
    assert "excerpt view" in block
    assert "Cite a chunk with its [n]." in block


def test_documents_render_as_excerpt_blocks() -> None:
    registry = CitationRegistry()

    block = render_search_context(
        [_document(1, "Q3", [1], source="Slack · #launch")], registry
    )

    assert block is not None
    assert '<document title="Q3" source="Slack · #launch" view="excerpt">' in block
    assert "</document>" in block


def test_same_passage_reuses_label_across_calls() -> None:
    registry = CitationRegistry()
    document = _document(1, "Doc", [880])

    render_search_context([document], registry)
    block = render_search_context([document], registry)

    assert block is not None
    assert "[1] text 880" in block
    assert registry.next_n == 2
