"""Tests for mapping a DocumentHit to a renderable document."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.retrieval.adapter import (
    to_renderable_document,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.models import (
    ChunkHit,
    DocumentHit,
)

pytestmark = pytest.mark.unit


def test_maps_identity_source_and_passages() -> None:
    hit = DocumentHit(
        document_id=42,
        title="Q3 Launch Notes",
        document_type="SLACK_CONNECTOR",
        metadata={},
        score=0.9,
        chunks=[
            ChunkHit(chunk_id=880, content="a", position=4, score=0.9),
            ChunkHit(chunk_id=881, content="b", position=7, score=0.5),
        ],
    )

    document = to_renderable_document(hit)

    assert document.title == "Q3 Launch Notes"
    assert document.source == "Slack"
    assert [(p.locator["chunk_id"], p.content) for p in document.passages] == [
        (880, "a"),
        (881, "b"),
    ]
    assert all(p.locator["document_id"] == 42 for p in document.passages)


def test_document_with_no_chunks_maps_to_no_passages() -> None:
    hit = DocumentHit(
        document_id=1,
        title="Empty",
        document_type=None,
        metadata={},
        score=0.0,
        chunks=[],
    )

    assert to_renderable_document(hit).passages == []
