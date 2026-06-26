"""Tests for the build_context pipeline (rerank → adapt → render)."""

from __future__ import annotations

from typing import Any

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.retrieval.models import (
    ChunkHit,
    DocumentHit,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.service import build_context

pytestmark = pytest.mark.unit


def _hit(document_id: int, chunk_id: int) -> DocumentHit:
    return DocumentHit(
        document_id=document_id,
        title=f"Doc {document_id}",
        document_type="FILE",
        metadata={},
        score=1.0 / document_id,
        chunks=[
            ChunkHit(
                chunk_id=chunk_id, content=f"text {chunk_id}", position=0, score=1.0
            )
        ],
    )


def test_no_hits_renders_nothing() -> None:
    assert build_context("q", [], CitationRegistry()) is None


def test_renders_block_and_registers_labels_in_order() -> None:
    registry = CitationRegistry()

    block = build_context("q", [_hit(1, 880), _hit(2, 12)], registry)

    assert block is not None
    assert "[1] text 880" in block
    assert "[2] text 12" in block
    assert registry.resolve(1).locator == {"document_id": 1, "chunk_id": 880}
    assert registry.resolve(2).locator == {"document_id": 2, "chunk_id": 12}


class _ReverseReranker:
    """Stand-in reranker that simply reverses document order."""

    def rerank_documents(
        self, query_text: str, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return list(reversed(documents))


def test_reranker_reorders_documents_before_labeling() -> None:
    registry = CitationRegistry()

    block = build_context(
        "q", [_hit(1, 880), _hit(2, 12)], registry, reranker=_ReverseReranker()
    )

    assert block is not None
    # Reversed: doc 2 now renders first and gets [1].
    assert registry.resolve(1).locator == {"document_id": 2, "chunk_id": 12}
    assert registry.resolve(2).locator == {"document_id": 1, "chunk_id": 880}
