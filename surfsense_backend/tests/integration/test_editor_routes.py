"""Phase A contract: editor read paths serve source_markdown and never
reconstruct or mutate the body from chunks."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Chunk,
    Document,
    DocumentStatus,
    DocumentType,
    SearchSpace,
    User,
)

pytestmark = pytest.mark.integration


async def _make_document(
    session: AsyncSession,
    search_space: SearchSpace,
    user: User,
    *,
    document_type: DocumentType = DocumentType.FILE,
    source_markdown: str | None = "# Title\n\nBody line.",
    content: str = "Body line.",
    status: dict | None = None,
) -> Document:
    doc = Document(
        title="Doc",
        document_type=document_type,
        document_metadata={},
        content=content,
        content_hash="hash-001",
        source_markdown=source_markdown,
        search_space_id=search_space.id,
        created_by_id=user.id,
        status=status or DocumentStatus.ready(),
    )
    session.add(doc)
    await session.flush()
    return doc


async def _add_chunks(session: AsyncSession, document: Document, texts: list[str]):
    for position, text in enumerate(texts):
        session.add(Chunk(content=text, position=position, document_id=document.id))
    await session.flush()


@pytest_asyncio.fixture
async def make_document(db_session, db_search_space, db_user):
    async def _make(**overrides):
        return await _make_document(db_session, db_search_space, db_user, **overrides)

    return _make


class TestGetEditorContent:
    async def test_returns_source_markdown_verbatim(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import get_editor_content

        doc = await make_document(source_markdown="# Real\n\nCanonical body.")

        result = await get_editor_content(
            db_search_space.id, doc.id, session=db_session, user=db_user
        )

        assert result["source_markdown"] == "# Real\n\nCanonical body."

    async def test_does_not_reconstruct_body_from_chunks(
        self, db_session, db_search_space, db_user, make_document
    ):
        """A ready document without source_markdown must not be rebuilt from chunks."""
        from app.routes.editor_routes import get_editor_content

        doc = await make_document(source_markdown=None)
        await _add_chunks(db_session, doc, ["chunk one", "chunk two"])

        with pytest.raises(HTTPException) as exc:
            await get_editor_content(
                db_search_space.id, doc.id, session=db_session, user=db_user
            )

        assert exc.value.status_code == 400
        await db_session.refresh(doc)
        assert doc.source_markdown is None

    async def test_processing_document_without_body_returns_409(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import get_editor_content

        doc = await make_document(
            source_markdown=None, status=DocumentStatus.processing()
        )

        with pytest.raises(HTTPException) as exc:
            await get_editor_content(
                db_search_space.id, doc.id, session=db_session, user=db_user
            )

        assert exc.value.status_code == 409

    async def test_failed_document_without_body_returns_422(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import get_editor_content

        doc = await make_document(
            source_markdown=None, status=DocumentStatus.failed("boom")
        )

        with pytest.raises(HTTPException) as exc:
            await get_editor_content(
                db_search_space.id, doc.id, session=db_session, user=db_user
            )

        assert exc.value.status_code == 422

    async def test_empty_note_initializes_to_empty_markdown(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import get_editor_content

        doc = await make_document(document_type=DocumentType.NOTE, source_markdown=None)

        result = await get_editor_content(
            db_search_space.id, doc.id, session=db_session, user=db_user
        )

        assert result["source_markdown"] == ""


class TestDownloadMarkdown:
    async def test_does_not_reconstruct_body_from_chunks(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import download_document_markdown

        doc = await make_document(source_markdown=None)
        await _add_chunks(db_session, doc, ["chunk one", "chunk two"])

        with pytest.raises(HTTPException) as exc:
            await download_document_markdown(
                db_search_space.id, doc.id, session=db_session, user=db_user
            )

        assert exc.value.status_code == 400


class TestExportDocument:
    async def test_does_not_reconstruct_body_from_chunks(
        self, db_session, db_search_space, db_user, make_document
    ):
        from app.routes.editor_routes import export_document
        from app.routes.reports_routes import ExportFormat

        doc = await make_document(source_markdown=None)
        await _add_chunks(db_session, doc, ["chunk one", "chunk two"])

        with pytest.raises(HTTPException) as exc:
            await export_document(
                db_search_space.id,
                doc.id,
                format=ExportFormat.PLAIN,
                session=db_session,
                user=db_user,
            )

        assert exc.value.status_code == 400
