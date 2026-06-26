"""Tests for the shared ``render_document`` (one ``<document>`` block)."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    render_document,
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


def test_returns_none_when_no_passages() -> None:
    registry = CitationRegistry()

    assert (
        render_document(_document(1, "Empty", []), view="excerpt", registry=registry)
        is None
    )


def test_excerpt_open_and_close_tags() -> None:
    registry = CitationRegistry()

    block = render_document(
        _document(1, "Q3 Launch Notes", [880], source="Slack · #launch"),
        view="excerpt",
        registry=registry,
    )

    assert block is not None
    assert block.startswith(
        '<document title="Q3 Launch Notes" source="Slack · #launch" view="excerpt">'
    )
    assert block.endswith("</document>")


def test_full_view_renders_view_attribute() -> None:
    registry = CitationRegistry()

    block = render_document(_document(1, "Doc", [880]), view="full", registry=registry)

    assert block is not None
    assert '<document title="Doc" view="full">' in block


def test_source_attribute_omitted_when_absent() -> None:
    registry = CitationRegistry()

    block = render_document(
        _document(1, "Plain", [1]), view="excerpt", registry=registry
    )

    assert block is not None
    assert block.startswith('<document title="Plain" view="excerpt">')


def test_registers_passages_with_chunk_locators() -> None:
    registry = CitationRegistry()

    render_document(
        _document(1, "Doc", [880], source="Slack"),
        view="excerpt",
        registry=registry,
    )

    entry = registry.resolve(1)
    assert entry is not None
    assert entry.source_type is CitationSourceType.KB_CHUNK
    assert entry.locator == {"document_id": 1, "chunk_id": 880}
    assert entry.display == {"title": "Doc", "source": "Slack"}


def test_passages_get_monotonic_labels() -> None:
    registry = CitationRegistry()

    block = render_document(
        _document(1, "Doc", [880, 881]), view="excerpt", registry=registry
    )

    assert block is not None
    assert "  [1] text 880" in block
    assert "  [2] text 881" in block


def test_multiline_passage_indents_under_label() -> None:
    registry = CitationRegistry()
    document = RenderableDocument(
        title="Doc",
        passages=[
            RenderablePassage(
                content="line one\nline two",
                locator={"document_id": 1, "chunk_id": 5},
            )
        ],
    )

    block = render_document(document, view="excerpt", registry=registry)

    assert block is not None
    assert "  [1] line one\n      line two" in block


def test_attribute_values_are_escaped() -> None:
    registry = CitationRegistry()

    block = render_document(
        _document(1, 'A & B <c> "d"', [1], source="x & y"),
        view="excerpt",
        registry=registry,
    )

    assert block is not None
    assert 'title="A &amp; B &lt;c&gt; &quot;d&quot;"' in block
    assert 'source="x &amp; y"' in block


def test_same_passage_reuses_label_across_calls() -> None:
    registry = CitationRegistry()
    document = _document(1, "Doc", [880])

    render_document(document, view="excerpt", registry=registry)
    render_document(document, view="full", registry=registry)

    assert registry.next_n == 2
