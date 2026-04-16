"""
File document processors orchestrating content extraction and indexing.

Delegates content extraction to ``app.etl_pipeline.EtlPipelineService`` and
keeps only orchestration concerns (notifications, logging, page limits, saving).
"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Log, Notification
from app.services.notification_service import NotificationService
from app.services.task_logging_service import TaskLoggingService

from ._helpers import update_document_from_connector
from ._save import save_file_document
from .markdown_processor import add_received_markdown_file_document

__all__ = [
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
    use_vision_llm: bool = False
    processing_mode: str = "basic"
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


async def _process_non_document_upload(ctx: _ProcessingContext) -> Document | None:
    """Extract content from a non-document file (plaintext/direct_convert/audio/image) via the unified ETL pipeline."""
    from app.etl_pipeline.etl_document import EtlRequest
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService
    from app.etl_pipeline.file_classifier import (
        FileCategory,
        classify_file as etl_classify,
    )

    await _notify(ctx, "parsing", "Processing file")
    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Processing file: {ctx.filename}",
        {"processing_stage": "extracting"},
    )

    vision_llm = None
    if ctx.use_vision_llm and etl_classify(ctx.filename) == FileCategory.IMAGE:
        from app.services.llm_service import get_vision_llm

        vision_llm = await get_vision_llm(ctx.session, ctx.search_space_id)

    etl_result = await EtlPipelineService(vision_llm=vision_llm).extract(
        EtlRequest(file_path=ctx.file_path, filename=ctx.filename)
    )

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    await _notify(ctx, "chunking")

    result = await add_received_markdown_file_document(
        ctx.session,
        ctx.filename,
        etl_result.markdown_content,
        ctx.search_space_id,
        ctx.user_id,
        ctx.connector,
    )
    if ctx.connector:
        await update_document_from_connector(result, ctx.connector, ctx.session)

    if result:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed file: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": etl_result.content_type,
                "etl_service": etl_result.etl_service,
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"File already exists (duplicate): {ctx.filename}",
            {"duplicate_detected": True, "file_type": etl_result.content_type},
        )
    return result


# ---------------------------------------------------------------------------
# Document file processing (ETL service dispatch)
# ---------------------------------------------------------------------------


async def _process_document_upload(ctx: _ProcessingContext) -> Document | None:
    """Route a document file to the configured ETL service via the unified pipeline."""
    from app.etl_pipeline.etl_document import EtlRequest, ProcessingMode
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService
    from app.services.page_limit_service import PageLimitExceededError, PageLimitService

    mode = ProcessingMode.coerce(ctx.processing_mode)
    page_limit_service = PageLimitService(ctx.session)
    estimated_pages = _estimate_pages_safe(page_limit_service, ctx.file_path)
    billable_pages = estimated_pages * mode.page_multiplier

    await ctx.task_logger.log_task_progress(
        ctx.log_entry,
        f"Estimated {estimated_pages} pages for file: {ctx.filename}",
        {
            "estimated_pages": estimated_pages,
            "billable_pages": billable_pages,
            "processing_mode": mode.value,
            "file_type": "document",
        },
    )

    try:
        await page_limit_service.check_page_limit(ctx.user_id, billable_pages)
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
                "billable_pages": billable_pages,
                "processing_mode": mode.value,
            },
        )
        with contextlib.suppress(Exception):
            os.unlink(ctx.file_path)
        raise HTTPException(status_code=403, detail=str(e)) from e

    await _notify(ctx, "parsing", "Extracting content")

    etl_result = await EtlPipelineService().extract(
        EtlRequest(
            file_path=ctx.file_path,
            filename=ctx.filename,
            estimated_pages=estimated_pages,
            processing_mode=mode,
        )
    )

    with contextlib.suppress(Exception):
        os.unlink(ctx.file_path)

    await _notify(ctx, "chunking")

    result = await save_file_document(
        ctx.session,
        ctx.filename,
        etl_result.markdown_content,
        ctx.search_space_id,
        ctx.user_id,
        etl_result.etl_service,
        ctx.connector,
        enable_summary=ctx.enable_summary,
    )

    if result:
        await page_limit_service.update_page_usage(
            ctx.user_id, billable_pages, allow_exceed=True
        )
        if ctx.connector:
            await update_document_from_connector(result, ctx.connector, ctx.session)
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Successfully processed file: {ctx.filename}",
            {
                "document_id": result.id,
                "content_hash": result.content_hash,
                "file_type": "document",
                "etl_service": etl_result.etl_service,
                "pages_processed": estimated_pages,
                "billable_pages": billable_pages,
                "processing_mode": mode.value,
            },
        )
    else:
        await ctx.task_logger.log_task_success(
            ctx.log_entry,
            f"Document already exists (duplicate): {ctx.filename}",
            {
                "duplicate_detected": True,
                "file_type": "document",
                "etl_service": etl_result.etl_service,
            },
        )
    return result


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
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
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
        use_vision_llm=use_vision_llm,
        processing_mode=processing_mode,
    )

    try:
        from app.etl_pipeline.file_classifier import (
            FileCategory as EtlFileCategory,
            classify_file as etl_classify,
        )

        category = etl_classify(filename)

        if category == EtlFileCategory.DOCUMENT:
            return await _process_document_upload(ctx)
        return await _process_non_document_upload(ctx)

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
    search_space_id: int,
    session: AsyncSession,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry: Log,
    notification: Notification | None,
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
) -> tuple[str, str, int]:
    """
    Extract markdown content from a file regardless of type.

    Returns:
        Tuple of (markdown_content, etl_service_name, billable_pages).
    """
    from app.etl_pipeline.etl_document import EtlRequest, ProcessingMode
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService
    from app.etl_pipeline.file_classifier import (
        FileCategory,
        classify_file as etl_classify,
    )

    mode = ProcessingMode.coerce(processing_mode)
    category = etl_classify(filename)
    estimated_pages = 0
    billable_pages = 0

    if notification:
        stage_messages = {
            FileCategory.PLAINTEXT: "Reading file",
            FileCategory.DIRECT_CONVERT: "Converting file",
            FileCategory.AUDIO: "Transcribing audio",
            FileCategory.IMAGE: "Analyzing image",
            FileCategory.UNSUPPORTED: "Unsupported file type",
            FileCategory.DOCUMENT: "Extracting content",
        }
        await NotificationService.document_processing.notify_processing_progress(
            session,
            notification,
            stage="parsing",
            stage_message=stage_messages.get(category, "Processing"),
        )

    await task_logger.log_task_progress(
        log_entry,
        f"Processing {category.value} file: {filename}",
        {"file_type": category.value, "processing_stage": "extracting"},
    )

    if category == FileCategory.DOCUMENT:
        from app.services.page_limit_service import PageLimitService

        page_limit_service = PageLimitService(session)
        estimated_pages = _estimate_pages_safe(page_limit_service, file_path)
        billable_pages = estimated_pages * mode.page_multiplier
        await page_limit_service.check_page_limit(user_id, billable_pages)

    vision_llm = None
    if use_vision_llm and category == FileCategory.IMAGE:
        from app.services.llm_service import get_vision_llm

        vision_llm = await get_vision_llm(session, search_space_id)

    result = await EtlPipelineService(vision_llm=vision_llm).extract(
        EtlRequest(
            file_path=file_path,
            filename=filename,
            estimated_pages=estimated_pages,
            processing_mode=mode,
        )
    )

    with contextlib.suppress(Exception):
        os.unlink(file_path)

    if not result.markdown_content or not result.markdown_content.strip():
        raise RuntimeError(f"Failed to extract content from file: {filename}")

    return result.markdown_content, result.etl_service, billable_pages


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
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
) -> Document | None:
    """
    Process file and update existing pending document (2-phase pattern).

    Phase 1 (API layer): Created document with pending status.
    Phase 2 (this function): Process file and update document to ready/failed.

    Page usage is deferred until after dedup check and successful indexing
    to avoid charging for duplicate or failed uploads.
    """
    from app.indexing_pipeline.adapters.file_upload_adapter import (
        UploadDocumentAdapter,
    )
    from app.services.llm_service import get_user_long_context_llm
    from app.utils.document_converters import generate_content_hash

    from .base import check_duplicate_document

    doc_id = document.id

    try:
        markdown_content, etl_service, billable_pages = await _extract_file_content(
            file_path,
            filename,
            search_space_id,
            session,
            user_id,
            task_logger,
            log_entry,
            notification,
            use_vision_llm=use_vision_llm,
            processing_mode=processing_mode,
        )

        if not markdown_content:
            raise RuntimeError(f"Failed to extract content from file: {filename}")

        content_hash = generate_content_hash(markdown_content, search_space_id)
        existing_by_content = await check_duplicate_document(session, content_hash)
        if existing_by_content and existing_by_content.id != doc_id:
            logging.info(
                f"Duplicate content detected for {filename}, "
                f"matches document {existing_by_content.id}"
            )
            return None

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

        if billable_pages > 0:
            from app.services.page_limit_service import PageLimitService

            page_limit_service = PageLimitService(session)
            await page_limit_service.update_page_usage(
                user_id, billable_pages, allow_exceed=True
            )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed file: {filename}",
            {
                "document_id": doc_id,
                "content_hash": content_hash,
                "file_type": etl_service,
                "billable_pages": billable_pages,
                "processing_mode": processing_mode,
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
