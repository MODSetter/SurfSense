"""Phase E.1 contract: the by-chunk resolve API exposes chunk char spans and
derives the cited chunk's line range from source_markdown."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Chunk, Document, DocumentStatus, DocumentType, SearchSpace, User

pytestmark = pytest.mark.integration

_BODY = "alpha\nbravo\ncharlie\ndelta"


async def _make_document(
    session: AsyncSession,
    search_space: SearchSpace,
    user: User,
    *,
    source_markdown: str = _BODY,
) -> Document:
    doc = Document(
        title="Doc",
        document_type=DocumentType.FILE,
        document_metadata={},
        content=source_markdown,
        content_hash="hash-by-chunk",
        source_markdown=source_markdown,
        search_space_id=search_space.id,
        created_by_id=user.id,
        status=DocumentStatus.ready(),
    )
    session.add(doc)
    await session.flush()
    return doc


async def _add_chunk(
    session: AsyncSession,
    document: Document,
    *,
    content: str,
    position: int,
    start_char: int | None,
    end_char: int | None,
) -> Chunk:
    chunk = Chunk(
        content=content,
        position=position,
        document_id=document.id,
        start_char=start_char,
        end_char=end_char,
    )
    session.add(chunk)
    await session.flush()
    return chunk


@pytest_asyncio.fixture
async def make_document(db_session, db_search_space, db_user):
    async def _make(**overrides):
        return await _make_document(db_session, db_search_space, db_user, **overrides)

    return _make


async def test_cited_line_range_derived_from_spans(
    db_session, db_search_space, db_user, make_document
):
    from app.routes.documents_routes import get_document_by_chunk_id

    doc = await make_document()
    await _add_chunk(
        db_session, doc, content="alpha\nbravo\n", position=0, start_char=0, end_char=12
    )
    cited = await _add_chunk(
        db_session,
        doc,
        content="charlie\ndelta",
        position=1,
        start_char=12,
        end_char=len(_BODY),
    )

    result = await get_document_by_chunk_id(
        cited.id, chunk_window=5, session=db_session, user=db_user
    )

    assert result.cited_start_line == 3
    assert result.cited_end_line == 4


async def test_chunk_spans_exposed_in_response(
    db_session, db_search_space, db_user, make_document
):
    from app.routes.documents_routes import get_document_by_chunk_id

    doc = await make_document()
    cited = await _add_chunk(
        db_session, doc, content="alpha\nbravo\n", position=0, start_char=0, end_char=12
    )

    result = await get_document_by_chunk_id(
        cited.id, chunk_window=5, session=db_session, user=db_user
    )

    chunk = next(c for c in result.chunks if c.id == cited.id)
    assert chunk.start_char == 0
    assert chunk.end_char == 12


async def test_cited_line_range_null_without_spans(
    db_session, db_search_space, db_user, make_document
):
    from app.routes.documents_routes import get_document_by_chunk_id

    doc = await make_document()
    cited = await _add_chunk(
        db_session, doc, content="alpha", position=0, start_char=None, end_char=None
    )

    result = await get_document_by_chunk_id(
        cited.id, chunk_window=5, session=db_session, user=db_user
    )

    assert result.cited_start_line is None
    assert result.cited_end_line is None
