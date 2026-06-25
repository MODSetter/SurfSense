"""Tests for the <retrieved_context> renderer and its citation registration."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.retrieved_context import (
    RetrievedDocument,
    RetrievedPassage,
    render_retrieved_context,
)

pytestmark = pytest.mark.unit


def _document(
    document_id: int,
    title: str,
    chunk_ids: list[int],
    *,
    source_label: str | None = None,
) -> RetrievedDocument:
    return RetrievedDocument(
        document_id=document_id,
        title=title,
        source_label=source_label,
        passages=[
            RetrievedPassage(document_id=document_id, chunk_id=cid, content=f"text {cid}")
            for cid in chunk_ids
        ],
    )


def test_returns_none_when_nothing_to_show() -> None:
    registry = CitationRegistry()

    assert render_retrieved_context([], registry) is None
    assert render_retrieved_context([_document(1, "Empty", [])], registry) is None


def test_assigns_monotonic_labels_across_documents() -> None:
    registry = CitationRegistry()

    block = render_retrieved_context(
        [
            _document(1, "Q3 Launch Notes", [880, 881], source_label="Slack"),
            _document(2, "Timeline", [12], source_label="Notion"),
        ],
        registry,
    )

    assert block is not None
    assert "[1] text 880" in block
    assert "[2] text 881" in block
    assert "[3] text 12" in block


def test_registers_passages_with_chunk_locators() -> None:
    registry = CitationRegistry()

    render_retrieved_context([_document(1, "Doc", [880])], registry)

    entry = registry.resolve(1)
    assert entry is not None
    assert entry.source_type is CitationSourceType.KB_CHUNK
    assert entry.locator == {"document_id": 1, "chunk_id": 880}
    assert entry.display["title"] == "Doc"


def test_header_shows_source_when_present() -> None:
    registry = CitationRegistry()

    block = render_retrieved_context(
        [
            _document(1, "Q3", [1], source_label="Slack · #launch"),
            _document(2, "Plan", [2]),
        ],
        registry,
    )

    assert block is not None
    assert 'Document: "Q3"  (Slack · #launch)' in block
    assert 'Document: "Plan"' in block


def test_wraps_block_and_explains_chunk_vs_document() -> None:
    registry = CitationRegistry()

    block = render_retrieved_context([_document(1, "Doc", [1])], registry)

    assert block is not None
    assert block.startswith("<retrieved_context>")
    assert block.endswith("</retrieved_context>")
    assert "Cite a chunk with [n]." in block


def test_multiline_passage_is_indented_under_label() -> None:
    registry = CitationRegistry()
    document = RetrievedDocument(
        document_id=1,
        title="Doc",
        passages=[RetrievedPassage(document_id=1, chunk_id=5, content="line one\nline two")],
    )

    block = render_retrieved_context([document], registry)

    assert block is not None
    assert "  [1] line one\n      line two" in block


def test_continuation_indent_tracks_label_width() -> None:
    registry = CitationRegistry()
    # Burn labels 1..9 so the tenth passage renders as [10] (a 7-char label).
    documents = [_document(i, f"Doc {i}", [i]) for i in range(1, 10)]
    documents.append(
        RetrievedDocument(
            document_id=10,
            title="Doc 10",
            passages=[
                RetrievedPassage(document_id=10, chunk_id=10, content="line one\nline two")
            ],
        )
    )

    block = render_retrieved_context(documents, registry)

    assert block is not None
    assert "  [10] line one\n       line two" in block


def test_same_passage_reuses_label_across_calls() -> None:
    registry = CitationRegistry()
    document = _document(1, "Doc", [880])

    render_retrieved_context([document], registry)
    block = render_retrieved_context([document], registry)

    assert block is not None
    assert "[1] text 880" in block
    assert registry.next_n == 2
