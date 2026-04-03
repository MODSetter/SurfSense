"""
Editor routes for document editing with markdown (Plate.js frontend).
Includes multi-format export (PDF, DOCX, HTML, LaTeX, EPUB, ODT, plain text).
"""

import asyncio
import io
import logging
import os
import tempfile
from datetime import UTC, datetime
from typing import Any

import pypandoc
import typst
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Chunk, Document, DocumentType, Permission, User, get_async_session
from app.routes.reports_routes import (
    _FILE_EXTENSIONS,
    _MEDIA_TYPES,
    ExportFormat,
    _normalize_latex_delimiters,
    _strip_wrapping_code_fences,
)
from app.templates.export_helpers import (
    get_html_css_path,
    get_reference_docx_path,
    get_typst_template_path,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search-spaces/{search_space_id}/documents/{document_id}/editor-content")
async def get_editor_content(
    search_space_id: int,
    document_id: int,
    max_length: int | None = Query(
        None, description="Truncate source_markdown to this many characters"
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get document content for editing.

    Returns source_markdown for the Plate.js editor.
    Falls back to blocknote_document → markdown conversion, then chunk reconstruction.

    Requires DOCUMENTS_READ permission.
    """
    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this search space",
    )

    result = await session.execute(
        select(Document).filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    count_result = await session.execute(
        select(func.count()).select_from(Chunk).filter(Chunk.document_id == document_id)
    )
    chunk_count = count_result.scalar() or 0

    def _build_response(md: str) -> dict:
        size_bytes = len(md.encode("utf-8"))
        truncated = False
        output_md = md
        if max_length is not None and size_bytes > max_length:
            output_md = md[:max_length]
            truncated = True
        return {
            "document_id": document.id,
            "title": document.title,
            "document_type": document.document_type.value,
            "source_markdown": output_md,
            "content_size_bytes": size_bytes,
            "chunk_count": chunk_count,
            "truncated": truncated,
            "updated_at": document.updated_at.isoformat()
            if document.updated_at
            else None,
        }

    if document.source_markdown is not None:
        return _build_response(document.source_markdown)

    if document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        markdown = blocknote_to_markdown(document.blocknote_document)
        if markdown:
            document.source_markdown = markdown
            await session.commit()
            return _build_response(markdown)

    if document.document_type == DocumentType.NOTE:
        empty_markdown = ""
        document.source_markdown = empty_markdown
        await session.commit()
        return _build_response(empty_markdown)

    chunk_contents_result = await session.execute(
        select(Chunk.content)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.id)
    )
    chunk_contents = chunk_contents_result.scalars().all()

    if not chunk_contents:
        raise HTTPException(
            status_code=400,
            detail="This document has no content and cannot be edited. Please re-upload to enable editing.",
        )

    markdown_content = "\n\n".join(chunk_contents)

    if not markdown_content.strip():
        raise HTTPException(
            status_code=400,
            detail="This document has empty content and cannot be edited.",
        )

    document.source_markdown = markdown_content
    await session.commit()

    return _build_response(markdown_content)


@router.get(
    "/search-spaces/{search_space_id}/documents/{document_id}/download-markdown"
)
async def download_document_markdown(
    search_space_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Download the full document content as a .md file.
    Reconstructs markdown from source_markdown or chunks.
    """
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this search space",
    )

    result = await session.execute(
        select(Document).filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    markdown: str | None = document.source_markdown
    if markdown is None and document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        markdown = blocknote_to_markdown(document.blocknote_document)
    if markdown is None:
        chunk_contents_result = await session.execute(
            select(Chunk.content)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.id)
        )
        chunk_contents = chunk_contents_result.scalars().all()
        if chunk_contents:
            markdown = "\n\n".join(chunk_contents)

    if not markdown or not markdown.strip():
        raise HTTPException(
            status_code=400, detail="Document has no content to download"
        )

    safe_title = (
        "".join(
            c if c.isalnum() or c in " -_" else "_"
            for c in (document.title or "document")
        ).strip()[:80]
        or "document"
    )

    return StreamingResponse(
        io.BytesIO(markdown.encode("utf-8")),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )


@router.post("/search-spaces/{search_space_id}/documents/{document_id}/save")
async def save_document(
    search_space_id: int,
    document_id: int,
    data: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Save document markdown and trigger reindexing.
    Called when user clicks 'Save & Exit'.

    Accepts { "source_markdown": "...", "title": "..." (optional) }.

    Requires DOCUMENTS_UPDATE permission.
    """
    from app.tasks.celery_tasks.document_reindex_tasks import reindex_document_task

    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_UPDATE.value,
        "You don't have permission to update documents in this search space",
    )

    result = await session.execute(
        select(Document).filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    source_markdown = data.get("source_markdown")
    if source_markdown is None:
        raise HTTPException(status_code=400, detail="source_markdown is required")

    if not isinstance(source_markdown, str):
        raise HTTPException(status_code=400, detail="source_markdown must be a string")

    # For NOTE type, extract title from first heading line if present
    if document.document_type == DocumentType.NOTE:
        # If the frontend sends a title, use it; otherwise extract from markdown
        new_title = data.get("title")
        if not new_title:
            # Extract title from the first line of markdown (# Heading)
            for line in source_markdown.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# "):
                    new_title = stripped[2:].strip()
                    break
                elif stripped:
                    # First non-empty non-heading line
                    new_title = stripped[:100]
                    break

        if new_title:
            document.title = new_title.strip()
        else:
            document.title = "Untitled"

    # Save source_markdown
    document.source_markdown = source_markdown
    document.updated_at = datetime.now(UTC)
    document.content_needs_reindexing = True

    await session.commit()

    # Queue reindex task
    reindex_document_task.delay(document_id, str(user.id))

    return {
        "status": "saved",
        "document_id": document_id,
        "message": "Document saved and will be reindexed in the background",
        "updated_at": document.updated_at.isoformat(),
    }


@router.get("/search-spaces/{search_space_id}/documents/{document_id}/export")
async def export_document(
    search_space_id: int,
    document_id: int,
    format: ExportFormat = Query(
        ExportFormat.PDF,
        description="Export format: pdf, docx, html, latex, epub, odt, or plain",
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Export a document in the requested format (reuses the report export pipeline)."""
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this search space",
    )

    result = await session.execute(
        select(Document).filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    markdown_content: str | None = document.source_markdown
    if markdown_content is None and document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        markdown_content = blocknote_to_markdown(document.blocknote_document)
    if markdown_content is None:
        chunk_contents_result = await session.execute(
            select(Chunk.content)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.id)
        )
        chunk_contents = chunk_contents_result.scalars().all()
        if chunk_contents:
            markdown_content = "\n\n".join(chunk_contents)

    if not markdown_content or not markdown_content.strip():
        raise HTTPException(status_code=400, detail="Document has no content to export")

    markdown_content = _strip_wrapping_code_fences(markdown_content)
    markdown_content = _normalize_latex_delimiters(markdown_content)

    doc_title = document.title or "Document"
    formatted_date = (
        document.created_at.strftime("%B %d, %Y") if document.created_at else ""
    )
    input_fmt = "gfm+tex_math_dollars"
    meta_args = ["-M", f"title:{doc_title}", "-M", f"date:{formatted_date}"]

    def _convert_and_read() -> bytes:
        if format == ExportFormat.PDF:
            typst_template = str(get_typst_template_path())
            typst_markup: str = pypandoc.convert_text(
                markdown_content,
                "typst",
                format=input_fmt,
                extra_args=[
                    "--standalone",
                    f"--template={typst_template}",
                    "-V",
                    "mainfont:Libertinus Serif",
                    "-V",
                    "codefont:DejaVu Sans Mono",
                    *meta_args,
                ],
            )
            return typst.compile(typst_markup.encode("utf-8"))

        if format == ExportFormat.DOCX:
            return _pandoc_to_tempfile(
                format.value,
                [
                    "--standalone",
                    f"--reference-doc={get_reference_docx_path()}",
                    *meta_args,
                ],
            )

        if format == ExportFormat.HTML:
            html_str: str = pypandoc.convert_text(
                markdown_content,
                "html5",
                format=input_fmt,
                extra_args=[
                    "--standalone",
                    "--embed-resources",
                    f"--css={get_html_css_path()}",
                    "--syntax-highlighting=pygments",
                    *meta_args,
                ],
            )
            return html_str.encode("utf-8")

        if format == ExportFormat.EPUB:
            return _pandoc_to_tempfile("epub3", ["--standalone", *meta_args])

        if format == ExportFormat.ODT:
            return _pandoc_to_tempfile("odt", ["--standalone", *meta_args])

        if format == ExportFormat.LATEX:
            tex_str: str = pypandoc.convert_text(
                markdown_content,
                "latex",
                format=input_fmt,
                extra_args=["--standalone", *meta_args],
            )
            return tex_str.encode("utf-8")

        plain_str: str = pypandoc.convert_text(
            markdown_content,
            "plain",
            format=input_fmt,
            extra_args=["--wrap=auto", "--columns=80"],
        )
        return plain_str.encode("utf-8")

    def _pandoc_to_tempfile(output_format: str, extra_args: list[str]) -> bytes:
        fd, tmp_path = tempfile.mkstemp(suffix=f".{output_format}")
        os.close(fd)
        try:
            pypandoc.convert_text(
                markdown_content,
                output_format,
                format=input_fmt,
                extra_args=extra_args,
                outputfile=tmp_path,
            )
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)

    try:
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, _convert_and_read)
    except Exception as e:
        logger.exception("Document export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {e!s}") from e

    safe_title = (
        "".join(c if c.isalnum() or c in " -_" else "_" for c in doc_title).strip()[:80]
        or "document"
    )
    ext = _FILE_EXTENSIONS[format]

    return StreamingResponse(
        io.BytesIO(output),
        media_type=_MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.{ext}"'},
    )
