"""Indexing records char spans so a chunk addresses its exact slice of the body.

Uses the real chunker (only embeddings are faked) so the span/partition
invariants are exercised end to end.
"""

import pytest
from sqlalchemy import select

from app.db import Chunk, Document
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration

_BODY = (
    "# Report\n\n"
    + "Intro paragraph that is reasonably long and descriptive. " * 8
    + "\n\n| col a | col b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n\n"
    + "Closing paragraph with a different shape and more words to chunk. " * 8
)


async def _ordered_chunks(session, document_id) -> list[Chunk]:
    result = await session.execute(
        select(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.position, Chunk.id)
    )
    return list(result.scalars().all())


def _assert_spans_address_body(chunks: list[Chunk], body: str) -> None:
    for chunk in chunks:
        assert chunk.start_char is not None and chunk.end_char is not None
        assert body[chunk.start_char : chunk.end_char] == chunk.content
    assert "".join(c.content for c in chunks) == body


async def _index(session, connector_doc) -> int:
    service = IndexingPipelineService(session=session)
    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    await service.index(document, connector_doc)
    return document.id


async def _reload_body(session, document_id) -> str:
    result = await session.execute(select(Document).filter(Document.id == document_id))
    return result.scalars().first().source_markdown


@pytest.mark.usefixtures("patched_embed_texts")
async def test_scratch_index_records_spans_addressing_body(
    db_session, db_search_space, make_connector_document
):
    connector_doc = make_connector_document(
        search_space_id=db_search_space.id, source_markdown=_BODY
    )

    document_id = await _index(db_session, connector_doc)

    body = await _reload_body(db_session, document_id)
    chunks = await _ordered_chunks(db_session, document_id)

    assert len(chunks) > 1
    _assert_spans_address_body(chunks, body)


@pytest.mark.usefixtures("patched_embed_texts")
async def test_incremental_reindex_refreshes_shifted_spans(
    db_session, db_search_space, make_connector_document
):
    """Inserting text at the top shifts every later chunk's span; kept rows must
    have their spans refreshed, not left pointing at the old offsets."""
    service = IndexingPipelineService(session=db_session)

    original = make_connector_document(
        search_space_id=db_search_space.id, source_markdown=_BODY
    )
    prepared = await service.prepare_for_indexing([original])
    document_id = prepared[0].id
    await service.index(prepared[0], original)

    edited_body = "# Prepended heading\n\nA brand new opening paragraph.\n\n" + _BODY
    edited = make_connector_document(
        search_space_id=db_search_space.id, source_markdown=edited_body
    )
    prepared_again = await service.prepare_for_indexing([edited])
    assert prepared_again, "edited content should requeue the document"
    await service.index(prepared_again[0], edited)

    body = await _reload_body(db_session, document_id)
    chunks = await _ordered_chunks(db_session, document_id)

    assert body == edited_body
    _assert_spans_address_body(chunks, body)
