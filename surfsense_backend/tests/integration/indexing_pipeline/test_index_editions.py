"""Edit path: re-indexing a document diffs chunks instead of replacing them.

Unchanged paragraphs must keep their chunk rows (ids survive -> embeddings and
HNSW entries untouched), only new text is embedded, removed text is deleted,
and (position) keeps presentation order correct throughout.
"""

import pytest
from sqlalchemy import select

from app.db import Chunk, DocumentStatus
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration

_V1 = "Intro paragraph.\n\nBody paragraph.\n\nOutro paragraph."


@pytest.fixture
def paragraph_chunker(monkeypatch):
    """One chunk per markdown paragraph, so edits map to chunk-level diffs."""

    def _split(markdown, **_kwargs):
        return [p for p in markdown.split("\n\n") if p.strip()]

    monkeypatch.setattr(
        "app.indexing_pipeline.cache.cached_indexing.chunk_text", _split
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.cache.cached_indexing.chunk_text_hybrid", _split
    )


async def _index(service, connector_doc):
    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    await service.index(document, connector_doc)
    return document


async def _load_chunks(db_session, document_id):
    result = await db_session.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.position, Chunk.id)
    )
    return result.scalars().all()


@pytest.mark.usefixtures("paragraph_chunker")
async def test_edit_keeps_unchanged_rows_and_embeds_only_the_new_text(
    db_session,
    db_search_space,
    make_connector_document,
    patched_embed_texts,
):
    service = IndexingPipelineService(session=db_session)
    doc_v1 = make_connector_document(
        search_space_id=db_search_space.id, source_markdown=_V1
    )
    document = await _index(service, doc_v1)

    ids_v1 = {c.content: c.id for c in await _load_chunks(db_session, document.id)}
    patched_embed_texts.reset_mock()

    edited = "Intro paragraph.\n\nBody paragraph EDITED.\n\nOutro paragraph."
    doc_v2 = make_connector_document(
        search_space_id=db_search_space.id, source_markdown=edited
    )
    await _index(service, doc_v2)

    chunks = await _load_chunks(db_session, document.id)
    by_content = {c.content: c for c in chunks}

    # Untouched paragraphs keep their rows (same ids => embeddings reused,
    # no HNSW/GIN churn); the edited paragraph got a fresh row.
    assert by_content["Intro paragraph."].id == ids_v1["Intro paragraph."]
    assert by_content["Outro paragraph."].id == ids_v1["Outro paragraph."]
    assert "Body paragraph." not in by_content
    assert by_content["Body paragraph EDITED."].id not in ids_v1.values()

    # Exactly one embed call: the document summary plus only the edited text.
    (embedded_texts,) = patched_embed_texts.call_args.args
    assert embedded_texts == [edited, "Body paragraph EDITED."]

    assert [c.position for c in chunks] == [0, 1, 2]
    assert [c.content for c in chunks] == [
        "Intro paragraph.",
        "Body paragraph EDITED.",
        "Outro paragraph.",
    ]


@pytest.mark.usefixtures("paragraph_chunker", "patched_embed_texts")
async def test_head_insert_shifts_positions_without_new_rows_for_old_text(
    db_session,
    db_search_space,
    make_connector_document,
):
    service = IndexingPipelineService(session=db_session)
    document = await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id, source_markdown=_V1
        ),
    )
    ids_v1 = {c.content: c.id for c in await _load_chunks(db_session, document.id)}

    await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id,
            source_markdown="Brand new opener.\n\n" + _V1,
        ),
    )

    chunks = await _load_chunks(db_session, document.id)
    assert [c.content for c in chunks] == [
        "Brand new opener.",
        "Intro paragraph.",
        "Body paragraph.",
        "Outro paragraph.",
    ]
    assert [c.position for c in chunks] == [0, 1, 2, 3]
    # The three original rows survived the shift.
    surviving = {c.content: c.id for c in chunks if c.content in ids_v1}
    assert surviving == ids_v1


@pytest.mark.usefixtures("paragraph_chunker", "patched_embed_texts")
async def test_removed_paragraph_is_deleted_and_order_compacts(
    db_session,
    db_search_space,
    make_connector_document,
):
    service = IndexingPipelineService(session=db_session)
    document = await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id, source_markdown=_V1
        ),
    )
    ids_v1 = {c.content: c.id for c in await _load_chunks(db_session, document.id)}

    await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id,
            source_markdown="Intro paragraph.\n\nOutro paragraph.",
        ),
    )

    chunks = await _load_chunks(db_session, document.id)
    assert [(c.content, c.position) for c in chunks] == [
        ("Intro paragraph.", 0),
        ("Outro paragraph.", 1),
    ]
    assert chunks[0].id == ids_v1["Intro paragraph."]
    assert chunks[1].id == ids_v1["Outro paragraph."]


@pytest.mark.usefixtures("paragraph_chunker", "patched_embed_texts")
async def test_kill_switch_falls_back_to_full_replace(
    db_session,
    db_search_space,
    make_connector_document,
    monkeypatch,
):
    from app.config import config

    service = IndexingPipelineService(session=db_session)
    document = await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id, source_markdown=_V1
        ),
    )
    ids_v1 = {c.id for c in await _load_chunks(db_session, document.id)}

    monkeypatch.setattr(config, "CHUNK_RECONCILE_ENABLED", False)
    await _index(
        service,
        make_connector_document(
            search_space_id=db_search_space.id,
            source_markdown=_V1 + "\n\nAppended paragraph.",
        ),
    )

    chunks = await _load_chunks(db_session, document.id)
    # Legacy behavior: every row is recreated, even unchanged paragraphs.
    assert {c.id for c in chunks}.isdisjoint(ids_v1)
    assert [c.position for c in chunks] == [0, 1, 2, 3]
    assert DocumentStatus.is_state(document.status, DocumentStatus.READY)
