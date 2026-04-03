"""
File document processors orchestrating content extraction and indexing.

This module is the public entry point for file processing.  It delegates to
specialised sub-modules that each own a single concern:

- ``_constants``          — file type classification and configuration constants
- ``_helpers``            — document deduplication, migration, connector helpers
- ``_direct_converters``  — lossless file-to-markdown for csv/tsv/html
- ``_etl``               — ETL parsing strategies (Unstructured, LlamaCloud, Docling)
- ``_save``              — unified document creation / update logic
"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass, field
from logging import ERROR, getLogger

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import Document, Log, Notification
from app.services.notification_service import NotificationService
from app.services.task_logging_service import TaskLoggingService

from ._constants import FileCategory, classify_file
from ._direct_converters import convert_file_directly
from ._etl import (
    parse_with_docling,
    parse_with_llamacloud_retry,
    parse_with_unstructured,
)
from ._helpers import update_document_from_connector
from ._save import (
    add_received_file_document_using_docling,
    add_received_file_document_using_llamacloud,
    add_received_file_document_using_unstructured,
    save_file_document,
)
from .markdown_processor import add_received_markdown_file_document

# Re-export public API so existing ``from file_processors import …`` keeps working.
__all__ = [
    "add_received_file_document_using_docling",
    "add_received_file_document_using_llamacloud",
    "add_received_file_document_using_unstructured",
    "parse_with_llamacloud_retry",
    "process_file_in_background",
    "process_file_in_background_with_document",
    "save_file_document",
]


# ---------------------------------------------------------------------------
# Processing context (bundles parameters shared across handler functions)
# ---------------------------------------------------------------------------


@dataclass
class _ProcessingContext:
    session: AsyncSession
    file_path: str
    filename: str
    search_space_id: int
    user_id: str
    task_logger: TaskLoggingService
    log_entry: Log
    connector: dict | None = None
    notification: Notification | None = None
    enable_summary: bool = field(init=False)

    def __post_init__(self) -> None:
        self.enable_summary = (
            self.connector.get("enable_summary", True) if self.connector else True
        )


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------


async def _notify(
    ctx: _ProcessingContext,
    stage: str,
    stage_message: str | None = None,
    **kwargs,
) -> None:
    """Send a processing-progress notification if one is attached."""
    if not ctx.notification:
        return
    await NotificationService.document_processing.notify_processing_progress(
        ctx.session,
        ctx.notification,
        stage=stage,
        stage_message=stage_message,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Page-limit helpers
# ---------------------------------------------------------------------------


def _estimate_pages_safe(page_limit_service, file_path: str) -> int:
    """Estimate page count with a file-size fallback."""
    try:
        return page_limit_service.estimate_pages_before_processing(file_path)
    except Exception:
        file_size = os.path.getsize(file_path)
        return max(1, file_size // (80 * 1024))


async def _log_page_divergence(
    task_logger: TaskLoggingService,
    log_entry: Log,
    filename: str,
    estimated: int,
    actual: int,
    final: int,
) -> None:
    """Log a warning when the actual page count far exceeds the pre-estimate."""
    if actual > estimated * 1.5:
        await task_logger.log_task_progress(
            log_entry,
            f"Actual page count higher than estimate: {filename}",
            {
                "estimated_before": estimated,
                "actual_pages": actual,
                "using_count": final,
            },
        )


# ===================================================================
# Handlers for process_file_in_background (legacy / connector path)
# ===================================================================


async def _process_markdown_upload(ctx: _ProcessingContext) -> Document | None:
    """Read a markdown / text file and create or update a document."""
    await _notify(ctx, "parsing", "Reading file")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing markdown/text file: {ctx.filename}",
        {"file_type": "markdown", "processing_stage": "reading_file"},
    )

    with open(ctx.file_path, encoding="utf-8") as f:
        markdown_content = f.read()

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    await _notify(ctx, "chunking")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Creating document from markdown content: {ctx.filename}",
        {
            "processing_stage": "creating_document",
            "content_length": len(markdown_content),
        },
    )

    result = await add_received_markdown_file_document(
        ctx.session,
        ctx.filename,
        markdown_content,
        ctx.search_space_id,
        ctx.user_id,
        ctx.connector,
    )
    if ctx.connector:
        await update_document_from_connector(result, ctx.connector, ctx.session)

    if result:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed markdown file: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "markdown",
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Markdown file already exists (duplicate): {ctx.filename}",
            {"duplicate_detected": True, "file_type": "markdown"},
        )
    return result


async def _process_direct_convert_upload(ctx: _ProcessingContext) -> Document | None:
    """Convert a text-based file (csv/tsv/html) to markdown without ETL."""
    await _notify(ctx, "parsing", "Converting file")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Direct-converting file to markdown: {ctx.filename}",
        {"file_type": "direct_convert", "processing_stage": "converting"},
    )

    markdown_content = convert_file_directly(ctx.file_path, ctx.filename)

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    await _notify(ctx, "chunking")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Creating document from converted content: {ctx.filename}",
        {
            "processing_stage": "creating_document",
            "content_length": len(markdown_content),
        },
    )

    result = await add_received_markdown_file_document(
        ctx.session,
        ctx.filename,
        markdown_content,
        ctx.search_space_id,
        ctx.user_id,
        ctx.connector,
    )
    if ctx.connector:
        await update_document_from_connector(result, ctx.connector, ctx.session)

    if result:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully direct-converted file: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "direct_convert",
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Direct-converted file already exists (duplicate): {ctx.filename}",
            {"duplicate_detected": True, "file_type": "direct_convert"},
        )
    return result


async def _process_audio_upload(ctx: _ProcessingContext) -> Document | None:
    """Transcribe an audio file and create or update a document."""
    await _notify(ctx, "parsing", "Transcribing audio")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing audio file for transcription: {ctx.filename}",
        {"file_type": "audio", "processing_stage": "starting_transcription"},
    )

    stt_service_type = (
        "local"
        if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
        else "external"
    )

    if stt_service_type == "local":
        from app.services.stt_service import stt_service

        try:
            stt_result = stt_service.transcribe_file(ctx.file_path)
            transcribed_text = stt_result.get("text", "")
            if not transcribed_text:
                raise ValueError("Transcription returned empty text")
            transcribed_text = (
                f"# Transcription of {ctx.filename}\n\n{transcribed_text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to transcribe audio file {ctx.filename}: {e!s}",
            ) from e

        await ctx.task_logger.log_task_progress(
            ctx.log_entry,
            f"Local STT transcription completed: {ctx.filename}",
            {
                "processing_stage": "local_transcription_complete",
                "language": stt_result.get("language"),
                "confidence": stt_result.get("language_probability"),
                "duration": stt_result.get("duration"),
            },
        )
    else:
        from litellm import atranscription

        with open(ctx.file_path, "rb") as audio_file:
            transcription_kwargs: dict = {
                "model": app_config.STT_SERVICE,
                "file": audio_file,
                "api_key": app_config.STT_SERVICE_API_KEY,
            }
            if app_config.STT_SERVICE_API_BASE:
                transcription_kwargs["api_base"] = app_config.STT_SERVICE_API_BASE

            transcription_response = await atranscription(**transcription_kwargs)
            transcribed_text = transcription_response.get("text", "")
            if not transcribed_text:
                raise ValueError("Transcription returned empty text")

        transcribed_text = f"# Transcription of {ctx.filename}\n\n{transcribed_text}"

    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Transcription completed, creating document: {ctx.filename}",
        {
            "processing_stage": "transcription_complete",
            "transcript_length": len(transcribed_text),
        },
    )

    await _notify(ctx, "chunking")

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    result = await add_received_markdown_file_document(
        ctx.session,
        ctx.filename,
        transcribed_text,
        ctx.search_space_id,
        ctx.user_id,
        ctx.connector,
    )
    if ctx.connector:
        await update_document_from_connector(result, ctx.connector, ctx.session)

    if result:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully transcribed and processed audio file: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "audio",
                "transcript_length": len(transcribed_text),
                "stt_service": stt_service_type,
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Audio file transcript already exists (duplicate): {ctx.filename}",
            {"duplicate_detected": True, "file_type": "audio"},
        )
    return result


# ---------------------------------------------------------------------------
# Document file processing (ETL service dispatch)
# ---------------------------------------------------------------------------


async def _etl_unstructured(
    ctx: _ProcessingContext,
    page_limit_service,
    estimated_pages: int,
) -> Document | None:
    """Parse and save via the Unstructured ETL service."""
    await _notify(ctx, "parsing", "Extracting content")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing file with Unstructured ETL: {ctx.filename}",
        {
            "file_type": "document",
            "etl_service": "UNSTRUCTURED",
            "processing_stage": "loading",
        },
    )

    docs = await parse_with_unstructured(ctx.file_path)

    await _notify(ctx, "chunking", chunks_count=len(docs))
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Unstructured ETL completed, creating document: {ctx.filename}",
        {"processing_stage": "etl_complete", "elements_count": len(docs)},
    )

    actual_pages = page_limit_service.estimate_pages_from_elements(docs)
    final_pages = max(estimated_pages, actual_pages)
    await _log_page_divergence(
        ctx.task_logger,
        ctx.log_entry,
        ctx.filename,
        estimated_pages,
        actual_pages,
        final_pages,
    )

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    result = await add_received_file_document_using_unstructured(
        ctx.session,
        ctx.filename,
        docs,
        ctx.search_space_id,
        ctx.user_id,
        ctx.connector,
        enable_summary=ctx.enable_summary,
    )
    if ctx.connector:
        await update_document_from_connector(result, ctx.connector, ctx.session)

    if result:
        await page_limit_service.update_page_usage(
            ctx.user_id, final_pages, allow_exceed=True
        )
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed file with Unstructured: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "document",
                "etl_service": "UNSTRUCTURED",
                "pages_processed": final_pages,
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Document already exists (duplicate): {ctx.filename}",
            {
                "duplicate_detected": True,
                "file_type": "document",
                "etl_service": "UNSTRUCTURED",
            },
        )
    return result


async def _etl_llamacloud(
    ctx: _ProcessingContext,
    page_limit_service,
    estimated_pages: int,
) -> Document | None:
    """Parse and save via the LlamaCloud ETL service."""
    await _notify(ctx, "parsing", "Extracting content")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing file with LlamaCloud ETL: {ctx.filename}",
        {
            "file_type": "document",
            "etl_service": "LLAMACLOUD",
            "processing_stage": "parsing",
            "estimated_pages": estimated_pages,
        },
    )

    raw_result = await parse_with_llamacloud_retry(
        file_path=ctx.file_path,
        estimated_pages=estimated_pages,
        task_logger=ctx.task_logger,
        log_entry=ctx.log_entry,
    )

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    markdown_documents = await raw_result.aget_markdown_documents(split_by_page=False)

    await _notify(ctx, "chunking", chunks_count=len(markdown_documents))
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"LlamaCloud parsing completed, creating documents: {ctx.filename}",
        {
            "processing_stage": "parsing_complete",
            "documents_count": len(markdown_documents),
        },
    )

    if not markdown_documents:
        await ctx.task_logger.log_task_failure(
            ctx.log_entry,
            f"LlamaCloud parsing returned no documents: {ctx.filename}",
            "ETL service returned empty document list",
            {"error_type": "EmptyDocumentList", "etl_service": "LLAMACLOUD"},
        )
        raise ValueError(f"LlamaCloud parsing returned no documents for {ctx.filename}")

    actual_pages = page_limit_service.estimate_pages_from_markdown(markdown_documents)
    final_pages = max(estimated_pages, actual_pages)
    await _log_page_divergence(
        ctx.task_logger,
        ctx.log_entry,
        ctx.filename,
        estimated_pages,
        actual_pages,
        final_pages,
    )

    any_created = False
    last_doc: Document | None = None

    for doc in markdown_documents:
        doc_result = await add_received_file_document_using_llamacloud(
            ctx.session,
            ctx.filename,
            llamacloud_markdown_document=doc.text,
            search_space_id=ctx.search_space_id,
            user_id=ctx.user_id,
            connector=ctx.connector,
            enable_summary=ctx.enable_summary,
        )
        if doc_result:
            any_created = True
            last_doc = doc_result

    if any_created:
        await page_limit_service.update_page_usage(
            ctx.user_id, final_pages, allow_exceed=True
        )
        if ctx.connector:
            await update_document_from_connector(last_doc, ctx.connector, ctx.session)
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed file with LlamaCloud: {ctx.filename}",
            {
                "document_id": last_doc.id,
                "content_hash": last_doc.content_hash,
                "file_type": "document",
                "etl_service": "LLAMACLOUD",
                "pages_processed": final_pages,
                "documents_count": len(markdown_documents),
            },
        )
        return last_doc

    await ctx.task_logger.log_task_success(
        ctx.log_entry,
        f"Document already exists (duplicate): {ctx.filename}",
        {
            "duplicate_detected": True,
            "file_type": "document",
            "etl_service": "LLAMACLOUD",
            "documents_count": len(markdown_documents),
        },
    )
    return None


async def _etl_docling(
    ctx: _ProcessingContext,
    page_limit_service,
    estimated_pages: int,
) -> Document | None:
    """Parse and save via the Docling ETL service."""
    await _notify(ctx, "parsing", "Extracting content")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing file with Docling ETL: {ctx.filename}",
        {
            "file_type": "document",
            "etl_service": "DOCLING",
            "processing_stage": "parsing",
        },
    )

    content = await parse_with_docling(ctx.file_path, ctx.filename)

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Docling parsing completed, creating document: {ctx.filename}",
        {"processing_stage": "parsing_complete", "content_length": len(content)},
    )

    actual_pages = page_limit_service.estimate_pages_from_content_length(len(content))
    final_pages = max(estimated_pages, actual_pages)
    await _log_page_divergence(
        ctx.task_logger,
        ctx.log_entry,
        ctx.filename,
        estimated_pages,
        actual_pages,
        final_pages,
    )

    await _notify(ctx, "chunking")

    result = await add_received_file_document_using_docling(
        ctx.session,
        ctx.filename,
        docling_markdown_document=content,
        search_space_id=ctx.search_space_id,
        user_id=ctx.user_id,
        connector=ctx.connector,
        enable_summary=ctx.enable_summary,
    )

    if result:
        await page_limit_service.update_page_usage(
            ctx.user_id, final_pages, allow_exceed=True
        )
        if ctx.connector:
            await update_document_from_connector(result, ctx.connector, ctx.session)
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed file with Docling: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "document",
                "etl_service": "DOCLING",
                "pages_processed": final_pages,
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Document already exists (duplicate): {ctx.filename}",
            {
                "duplicate_detected": True,
                "file_type": "document",
                "etl_service": "DOCLING",
            },
        )
    return result


async def _process_document_upload(ctx: _ProcessingContext) -> Document | None:
    """Route a document file to the configured ETL service."""
    from app.services.page_limit_service import PageLimitExceededError, PageLimitService

    page_limit_service = PageLimitService(ctx.session)
    estimated_pages = _estimate_pages_safe(page_limit_service, ctx.file_path)

    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Estimated {estimated_pages} pages for file: {ctx.filename}",
        {"estimated_pages": estimated_pages, "file_type": "document"},
    )

    try:
        await page_limit_service.check_page_limit(ctx.user_id, estimated_pages)
    except PageLimitExceededError as e:
        await ctx.task_logger.log_task_failure(
            ctx.log_entry,
            f"Page limit exceeded before processing: {ctx.filename}",
            str(e),
            {
                "error_type": "PageLimitExceeded",
                "pages_used": e.pages_used,
                "pages_limit": e.pages_limit,
                "estimated_pages": estimated_pages,
            },
        )
        with contextlib.suppress(Exception):
            os.unlink(ctx.file_path)
        raise HTTPException(status_code=403, detail=str(e)) from e

    etl_dispatch = {
        "UNSTRUCTURED": _etl_unstructured,
        "LLAMACLOUD": _etl_llamacloud,
        "DOCLING": _etl_docling,
    }
    handler = etl_dispatch.get(app_config.ETL_SERVICE)
    if handler is None:
        raise RuntimeError(f"Unknown ETL_SERVICE: {app_config.ETL_SERVICE}")

    return await handler(ctx, page_limit_service, estimated_pages)


# ===================================================================
# Public orchestrators
# ===================================================================


async def process_file_in_background(
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
    connector: dict | None = None,
    notification: Notification | None = None,
) -> Document | None:
    ctx = _ProcessingContext(
        session=session,
        file_path=file_path,
        filename=filename,
        search_space_id=search_space_id,
        user_id=user_id,
        task_logger=task_logger,
        log_entry=log_entry,
        connector=connector,
        notification=notification,
    )

    try:
        category = classify_file(filename)

        if category == FileCategory.MARKDOWN:
            return await _process_markdown_upload(ctx)
        if category == FileCategory.DIRECT_CONVERT:
            return await _process_direct_convert_upload(ctx)
        if category == FileCategory.AUDIO:
            return await _process_audio_upload(ctx)
        return await _process_document_upload(ctx)

    except Exception as e:
        await session.rollback()

        from app.services.page_limit_service import PageLimitExceededError

        if isinstance(e, PageLimitExceededError):
            error_message = str(e)
        elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
            error_message = str(e.detail)
        else:
            error_message = f"Failed to process file: {filename}"

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            str(e),
            {"error_type": type(e).__name__, "filename": filename},
        )
        logging.error(f"Error processing file in background: {error_message}")
        raise


# ===================================================================
# 2-phase handler (process_file_in_background_with_document)
# ===================================================================


async def _extract_file_content(
    file_path: str,
    filename: str,
    session: AsyncSession,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry: Log,
    notification: Notification | None,
) -> tuple[str, str]:
    """
    Extract markdown content from a file regardless of type.

    Returns:
        Tuple of (markdown_content, etl_service_name).
    """
    category = classify_file(filename)

    if category == FileCategory.MARKDOWN:
        if notification:
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Reading file",
            )
        await task_logger.log_task_progress(
            log_entry,
            f"Processing markdown/text file: {filename}",
            {"file_type": "markdown", "processing_stage": "reading_file"},
        )
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        with contextlib.suppress(Exception):
            os.unlink(file_path)
        return content, "MARKDOWN"

    if category == FileCategory.DIRECT_CONVERT:
        if notification:
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Converting file",
            )
        await task_logger.log_task_progress(
            log_entry,
            f"Direct-converting file to markdown: {filename}",
            {"file_type": "direct_convert", "processing_stage": "converting"},
        )
        content = convert_file_directly(file_path, filename)
        with contextlib.suppress(Exception):
            os.unlink(file_path)
        return content, "DIRECT_CONVERT"

    if category == FileCategory.AUDIO:
        if notification:
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Transcribing audio",
            )
        await task_logger.log_task_progress(
            log_entry,
            f"Processing audio file for transcription: {filename}",
            {"file_type": "audio", "processing_stage": "starting_transcription"},
        )
        transcribed_text = await _transcribe_audio(file_path, filename)
        with contextlib.suppress(Exception):
            os.unlink(file_path)
        return transcribed_text, "AUDIO_TRANSCRIPTION"

    # Document file — use ETL service
    return await _extract_document_content(
        file_path,
        filename,
        session,
        user_id,
        task_logger,
        log_entry,
        notification,
    )


async def _transcribe_audio(file_path: str, filename: str) -> str:
    """Transcribe an audio file and return formatted markdown text."""
    stt_service_type = (
        "local"
        if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
        else "external"
    )

    if stt_service_type == "local":
        from app.services.stt_service import stt_service

        result = stt_service.transcribe_file(file_path)
        text = result.get("text", "")
        if not text:
            raise ValueError("Transcription returned empty text")
    else:
        from litellm import atranscription

        with open(file_path, "rb") as audio_file:
            kwargs: dict = {
                "model": app_config.STT_SERVICE,
                "file": audio_file,
                "api_key": app_config.STT_SERVICE_API_KEY,
            }
            if app_config.STT_SERVICE_API_BASE:
                kwargs["api_base"] = app_config.STT_SERVICE_API_BASE
            response = await atranscription(**kwargs)
            text = response.get("text", "")
            if not text:
                raise ValueError("Transcription returned empty text")

    return f"# Transcription of {filename}\n\n{text}"


async def _extract_document_content(
    file_path: str,
    filename: str,
    session: AsyncSession,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry: Log,
    notification: Notification | None,
) -> tuple[str, str]:
    """
    Parse a document file via the configured ETL service.

    Returns:
        Tuple of (markdown_content, etl_service_name).
    """
    from app.services.page_limit_service import PageLimitService

    page_limit_service = PageLimitService(session)

    try:
        estimated_pages = page_limit_service.estimate_pages_before_processing(file_path)
    except Exception:
        file_size = os.path.getsize(file_path)
        estimated_pages = max(1, file_size // (80 * 1024))

    await page_limit_service.check_page_limit(user_id, estimated_pages)

    etl_service = app_config.ETL_SERVICE
    markdown_content: str | None = None

    if notification:
        await NotificationService.document_processing.notify_processing_progress(
            session,
            notification,
            stage="parsing",
            stage_message="Extracting content",
        )

    if etl_service == "UNSTRUCTURED":
        from app.utils.document_converters import convert_document_to_markdown

        docs = await parse_with_unstructured(file_path)
        markdown_content = await convert_document_to_markdown(docs)
        actual_pages = page_limit_service.estimate_pages_from_elements(docs)
        final_pages = max(estimated_pages, actual_pages)
        await page_limit_service.update_page_usage(
            user_id, final_pages, allow_exceed=True
        )

    elif etl_service == "LLAMACLOUD":
        raw_result = await parse_with_llamacloud_retry(
            file_path=file_path,
            estimated_pages=estimated_pages,
            task_logger=task_logger,
            log_entry=log_entry,
        )
        markdown_documents = await raw_result.aget_markdown_documents(
            split_by_page=False
        )
        if not markdown_documents:
            raise RuntimeError(f"LlamaCloud parsing returned no documents: {filename}")
        markdown_content = markdown_documents[0].text
        await page_limit_service.update_page_usage(
            user_id, estimated_pages, allow_exceed=True
        )

    elif etl_service == "DOCLING":
        getLogger("docling.pipeline.base_pipeline").setLevel(ERROR)
        getLogger("docling.document_converter").setLevel(ERROR)
        getLogger("docling_core.transforms.chunker.hierarchical_chunker").setLevel(
            ERROR
        )

        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown_content = result.document.export_to_markdown()
        await page_limit_service.update_page_usage(
            user_id, estimated_pages, allow_exceed=True
        )

    else:
        raise RuntimeError(f"Unknown ETL_SERVICE: {etl_service}")

    with contextlib.suppress(Exception):
        os.unlink(file_path)

    if not markdown_content:
        raise RuntimeError(f"Failed to extract content from file: {filename}")

    return markdown_content, etl_service


async def process_file_in_background_with_document(
    document: Document,
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
    connector: dict | None = None,
    notification: Notification | None = None,
    should_summarize: bool = False,
) -> Document | None:
    """
    Process file and update existing pending document (2-phase pattern).

    Phase 1 (API layer): Created document with pending status.
    Phase 2 (this function): Process file and update document to ready/failed.
    """
    from app.indexing_pipeline.adapters.file_upload_adapter import (
        UploadDocumentAdapter,
    )
    from app.services.llm_service import get_user_long_context_llm
    from app.utils.document_converters import generate_content_hash

    from .base import check_duplicate_document

    doc_id = document.id

    try:
        # Step 1: extract content
        markdown_content, etl_service = await _extract_file_content(
            file_path,
            filename,
            session,
            user_id,
            task_logger,
            log_entry,
            notification,
        )

        if not markdown_content:
            raise RuntimeError(f"Failed to extract content from file: {filename}")

        # Step 2: duplicate check
        content_hash = generate_content_hash(markdown_content, search_space_id)
        existing_by_content = await check_duplicate_document(session, content_hash)
        if existing_by_content and existing_by_content.id != doc_id:
            logging.info(
                f"Duplicate content detected for {filename}, "
                f"matches document {existing_by_content.id}"
            )
            return None

        # Step 3: index via pipeline
        if notification:
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="chunking",
            )

        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        adapter = UploadDocumentAdapter(session)
        await adapter.index(
            markdown_content=markdown_content,
            filename=filename,
            etl_service=etl_service,
            search_space_id=search_space_id,
            user_id=user_id,
            llm=user_llm,
            should_summarize=should_summarize,
        )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed file: {filename}",
            {
                "document_id": doc_id,
                "content_hash": content_hash,
                "file_type": etl_service,
            },
        )
        return document

    except Exception as e:
        await session.rollback()

        from app.services.page_limit_service import PageLimitExceededError

        if isinstance(e, PageLimitExceededError):
            error_message = str(e)
        elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
            error_message = str(e.detail)
        else:
            error_message = f"Failed to process file: {filename}"

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            str(e),
            {
                "error_type": type(e).__name__,
                "filename": filename,
                "document_id": doc_id,
            },
        )
        logging.error(f"Error processing file with document: {error_message}")
        raise
