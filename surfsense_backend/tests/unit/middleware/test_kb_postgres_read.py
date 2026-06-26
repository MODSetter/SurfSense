"""Unit tests for the KB read path: full-view render + anonymous-doc loading.

DB-backed loads are exercised by the integration suite; here we lock the pure
pieces — ``render_full_document`` and the anonymous-upload branch of
``aload_document`` — which need no database.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.kb_postgres import (
    KBPostgresBackend,
    render_full_document,
)

pytestmark = pytest.mark.unit


def _backend(state: dict) -> KBPostgresBackend:
    return KBPostgresBackend(search_space_id=1, runtime=SimpleNamespace(state=state))


def test_render_full_document_uses_full_view_and_registers() -> None:
    registry = CitationRegistry()
    document = RenderableDocument(
        title="Launch Notes",
        source="Slack",
        passages=[
            RenderablePassage(
                content="push to March 10",
                locator={"document_id": 7, "chunk_id": 880},
            ),
        ],
    )

    rendered = render_full_document(document, registry)

    assert '<document title="Launch Notes" source="Slack" view="full">' in rendered
    assert "[1] push to March 10" in rendered
    entry = registry.resolve(1)
    assert entry is not None
    assert entry.locator == {"document_id": 7, "chunk_id": 880}


def test_render_full_document_reuses_search_label() -> None:
    """A chunk already registered from search keeps its [n] on a later full read."""
    registry = CitationRegistry()
    n = registry.register(
        CitationSourceType.KB_CHUNK,
        {"document_id": 7, "chunk_id": 880},
        {"title": "Launch Notes", "source": "Slack"},
    )
    document = RenderableDocument(
        title="Launch Notes",
        source="Slack",
        passages=[
            RenderablePassage(
                content="new chunk",
                locator={"document_id": 7, "chunk_id": 881},
            ),
            RenderablePassage(
                content="push to March 10",
                locator={"document_id": 7, "chunk_id": 880},
            ),
        ],
    )

    rendered = render_full_document(document, registry)

    assert f"[{n}] push to March 10" in rendered
    assert "[2] new chunk" in rendered


def test_render_full_document_empty_falls_back_to_notice() -> None:
    registry = CitationRegistry()
    document = RenderableDocument(title="Empty", passages=[])

    assert render_full_document(document, registry) == (
        "(This document has no readable content.)"
    )


async def test_aload_document_anonymous_upload() -> None:
    backend = _backend(
        {
            "kb_anon_doc": {
                "path": "/anon_upload.md",
                "title": "Quarterly Report",
                "chunks": [
                    {"chunk_id": -1, "content": "revenue grew"},
                    {"chunk_id": -2, "content": "costs fell"},
                ],
            }
        }
    )

    loaded = await backend.aload_document("/anon_upload.md")

    assert loaded is not None
    document, doc_id = loaded
    assert doc_id is None
    assert document.title == "Quarterly Report"
    assert [p.locator["chunk_id"] for p in document.passages] == [-1, -2]
    assert all(p.locator["document_id"] == -1 for p in document.passages)
    assert all(
        p.source_type is CitationSourceType.ANON_CHUNK for p in document.passages
    )


async def test_aload_document_unknown_path_returns_none() -> None:
    backend = _backend({})

    assert await backend.aload_document("/not/under/documents.md") is None
