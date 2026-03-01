"""Celery tasks for document processing."""

import asyncio
import logging
import os
from uuid import UUID

from app.celery_app import celery_app
from app.config import config
from app.services.notification_service import NotificationService
from app.services.task_logging_service import TaskLoggingService
from app.tasks.celery_tasks import get_celery_session_maker
from app.tasks.document_processors import (
    add_extension_received_document,
    add_youtube_video_document,
)

logger = logging.getLogger(__name__)

# ===== Redis heartbeat for document processing tasks =====
# Same mechanism as connector indexing heartbeats (search_source_connectors_routes.py).
# A background coroutine refreshes a Redis key every 60s with a 2-min TTL.
# If the Celery worker crashes, the coroutine dies, the key expires, and the
# stale_notification_cleanup_task detects the missing key and marks the
# notification + document as failed.
_doc_heartbeat_redis = None
HEARTBEAT_TTL_SECONDS = 120  # 2 minutes — same as connector indexing
HEARTBEAT_REFRESH_INTERVAL = 60  # Refresh every 60 seconds


def _get_doc_heartbeat_redis():
    """Get Redis client for document processing heartbeat."""
    import redis

    global _doc_heartbeat_redis
    if _doc_heartbeat_redis is None:
        _doc_heartbeat_redis = redis.from_url(
            config.REDIS_APP_URL, decode_responses=True
        )
    return _doc_heartbeat_redis


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for document processing heartbeat.

    Uses same key pattern as connector indexing: indexing:heartbeat:{notification_id}
    """
    return f"indexing:heartbeat:{notification_id}"


def _start_heartbeat(notification_id: int) -> None:
    """Set initial Redis heartbeat key for a document processing task."""
    try:
        key = _get_heartbeat_key(notification_id)
        _get_doc_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "started")
    except Exception as e:
        logger.warning(
            f"Failed to set initial heartbeat for notification {notification_id}: {e}"
        )


def _stop_heartbeat(notification_id: int) -> None:
    """Delete Redis heartbeat key when task completes (success or failure)."""
    try:
        key = _get_heartbeat_key(notification_id)
        _get_doc_heartbeat_redis().delete(key)
    except Exception:
        pass  # Key will expire on its own


async def _run_heartbeat_loop(notification_id: int):
    """Background coroutine that refreshes Redis heartbeat every 60 seconds.

    This keeps the heartbeat alive while the task is running.
    When the task finishes, this coroutine is cancelled via heartbeat_task.cancel().
    When the worker crashes, this coroutine dies with it and the key expires.
    """
    key = _get_heartbeat_key(notification_id)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_REFRESH_INTERVAL)
            try:
                _get_doc_heartbeat_redis().setex(key, HEARTBEAT_TTL_SECONDS, "alive")
            except Exception as e:
                logger.warning(
                    f"Failed to refresh heartbeat for notification {notification_id}: {e}"
                )
    except asyncio.CancelledError:
        pass  # Normal cancellation when task completes


@celery_app.task(name="process_extension_document", bind=True)
def process_extension_document_task(
    self, individual_document_dict, search_space_id: int, user_id: str
):
    """
    Celery task to process extension document.

    Args:
        individual_document_dict: Document data as dictionary
        search_space_id: ID of the search space
        user_id: ID of the user
    """
    # Create a new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_extension_document(
                individual_document_dict, search_space_id, user_id
            )
        )
    finally:
        loop.close()


async def _process_extension_document(
    individual_document_dict, search_space_id: int, user_id: str
):
    """Process extension document with new session."""
    from pydantic import BaseModel, ConfigDict, Field

    # Reconstruct the document object from dict
    # You'll need to define the proper model for this
    class DocumentMetadata(BaseModel):
        VisitedWebPageTitle: str
        VisitedWebPageURL: str
        BrowsingSessionId: str
        VisitedWebPageDateWithTimeInISOString: str
        VisitedWebPageReffererURL: str
        VisitedWebPageVisitDurationInMilliseconds: str

    class IndividualDocument(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        metadata: DocumentMetadata
        page_content: str = Field(alias="pageContent")

    individual_document = IndividualDocument(**individual_document_dict)

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

        # Truncate title for notification display
        page_title = individual_document.metadata.VisitedWebPageTitle[:50]
        if len(individual_document.metadata.VisitedWebPageTitle) > 50:
            page_title += "..."

        # Create notification for document processing
        notification = (
            await NotificationService.document_processing.notify_processing_started(
                session=session,
                user_id=UUID(user_id),
                document_type="EXTENSION",
                document_name=page_title,
                search_space_id=search_space_id,
            )
        )

        log_entry = await task_logger.log_task_start(
            task_name="process_extension_document",
            source="document_processor",
            message=f"Starting processing of extension document from {individual_document.metadata.VisitedWebPageTitle}",
            metadata={
                "document_type": "EXTENSION",
                "url": individual_document.metadata.VisitedWebPageURL,
                "title": individual_document.metadata.VisitedWebPageTitle,
                "user_id": user_id,
            },
        )

        try:
            # Update notification: parsing stage
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Reading page content",
            )

            result = await add_extension_received_document(
                session, individual_document, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed extension document: {individual_document.metadata.VisitedWebPageTitle}",
                    {"document_id": result.id, "content_hash": result.content_hash},
                )

                # Update notification on success
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Extension document already exists (duplicate): {individual_document.metadata.VisitedWebPageTitle}",
                    {"duplicate_detected": True},
                )

                # Update notification for duplicate
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Page already saved (duplicate)",
                    )
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process extension document: {individual_document.metadata.VisitedWebPageTitle}",
                str(e),
                {"error_type": type(e).__name__},
            )

            # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                )
            except Exception as notif_error:
                logger.error(
                    f"Failed to update notification on failure: {notif_error!s}"
                )

            logger.error(f"Error processing extension document: {e!s}")
            raise


@celery_app.task(name="process_youtube_video", bind=True)
def process_youtube_video_task(self, url: str, search_space_id: int, user_id: str):
    """
    Celery task to process YouTube video.

    Args:
        url: YouTube video URL
        search_space_id: ID of the search space
        user_id: ID of the user
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_process_youtube_video(url, search_space_id, user_id))
    finally:
        loop.close()


async def _process_youtube_video(url: str, search_space_id: int, user_id: str):
    """Process YouTube video with new session."""
    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

        # Extract video title from URL for notification (will be updated later)
        video_name = url.split("v=")[-1][:11] if "v=" in url else url

        # Create notification for document processing
        notification = (
            await NotificationService.document_processing.notify_processing_started(
                session=session,
                user_id=UUID(user_id),
                document_type="YOUTUBE_VIDEO",
                document_name=f"YouTube: {video_name}",
                search_space_id=search_space_id,
            )
        )

        # Start Redis heartbeat for stale task detection
        _start_heartbeat(notification.id)
        heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))

        log_entry = await task_logger.log_task_start(
            task_name="process_youtube_video",
            source="document_processor",
            message=f"Starting YouTube video processing for: {url}",
            metadata={"document_type": "YOUTUBE_VIDEO", "url": url, "user_id": user_id},
        )

        try:
            # Update notification: parsing (fetching transcript)
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Fetching video transcript",
            )

            result = await add_youtube_video_document(
                session, url, search_space_id, user_id, notification=notification
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed YouTube video: {result.title}",
                    {
                        "document_id": result.id,
                        "video_id": result.document_metadata.get("video_id"),
                        "content_hash": result.content_hash,
                    },
                )

                # Update notification on success
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"YouTube video document already exists (duplicate): {url}",
                    {"duplicate_detected": True},
                )

                # Update notification for duplicate
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Video already exists (duplicate)",
                    )
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process YouTube video: {url}",
                str(e),
                {"error_type": type(e).__name__},
            )

            # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                )
            except Exception as notif_error:
                logger.error(
                    f"Failed to update notification on failure: {notif_error!s}"
                )

            logger.error(f"Error processing YouTube video: {e!s}")
            raise
        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            heartbeat_task.cancel()
            _stop_heartbeat(notification.id)


@celery_app.task(name="process_file_upload", bind=True)
def process_file_upload_task(
    self, file_path: str, filename: str, search_space_id: int, user_id: str
):
    """
    Celery task to process uploaded file.

    Args:
        file_path: Path to the uploaded file
        filename: Original filename
        search_space_id: ID of the search space
        user_id: ID of the user
    """
    import traceback

    logger.info(
        f"[process_file_upload] Task started - file: {filename}, "
        f"search_space_id: {search_space_id}, user_id: {user_id}"
    )
    logger.info(f"[process_file_upload] File path: {file_path}")

    # Check if file exists and is accessible
    if not os.path.exists(file_path):
        logger.error(
            f"[process_file_upload] File does not exist: {file_path}. "
            "File may have been removed before syncing could start."
        )
        return

    try:
        file_size = os.path.getsize(file_path)
        logger.info(f"[process_file_upload] File size: {file_size} bytes")
    except Exception as e:
        logger.warning(f"[process_file_upload] Could not get file size: {e}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_file_upload(file_path, filename, search_space_id, user_id)
        )
        logger.info(
            f"[process_file_upload] Task completed successfully for: {filename}"
        )
    except Exception as e:
        logger.error(
            f"[process_file_upload] Task failed for {filename}: {e}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        raise
    finally:
        loop.close()


async def _process_file_upload(
    file_path: str, filename: str, search_space_id: int, user_id: str
):
    """Process file upload with new session."""
    from app.tasks.document_processors.file_processors import process_file_in_background

    logger.info(f"[_process_file_upload] Starting async processing for: {filename}")

    async with get_celery_session_maker()() as session:
        logger.info(f"[_process_file_upload] Database session created for: {filename}")
        task_logger = TaskLoggingService(session, search_space_id)

        # Get file size for notification metadata
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"[_process_file_upload] File size: {file_size} bytes")
        except Exception as e:
            logger.warning(f"[_process_file_upload] Could not get file size: {e}")
            file_size = None

        # Create notification for document processing
        logger.info(f"[_process_file_upload] Creating notification for: {filename}")
        notification = (
            await NotificationService.document_processing.notify_processing_started(
                session=session,
                user_id=UUID(user_id),
                document_type="FILE",
                document_name=filename,
                search_space_id=search_space_id,
                file_size=file_size,
            )
        )
        logger.info(
            f"[_process_file_upload] Notification created with ID: {notification.id if notification else 'None'}"
        )

        # Start Redis heartbeat for stale task detection
        _start_heartbeat(notification.id)
        heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))

        log_entry = await task_logger.log_task_start(
            task_name="process_file_upload",
            source="document_processor",
            message=f"Starting file processing for: {filename}",
            metadata={
                "document_type": "FILE",
                "filename": filename,
                "file_path": file_path,
                "user_id": user_id,
            },
        )

        try:
            result = await process_file_in_background(
                file_path,
                filename,
                search_space_id,
                user_id,
                session,
                task_logger,
                log_entry,
                notification=notification,
            )

            # Update notification on success
            if result:
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                )
            else:
                # Duplicate detected
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Document already exists (duplicate)",
                    )
                )

        except Exception as e:
            # Import here to avoid circular dependencies
            from fastapi import HTTPException

            from app.services.page_limit_service import PageLimitExceededError

            # Check if this is a page limit error (either direct or wrapped in HTTPException)
            page_limit_error: PageLimitExceededError | None = None
            if isinstance(e, PageLimitExceededError):
                page_limit_error = e
            elif (
                isinstance(e, HTTPException)
                and e.__cause__
                and isinstance(e.__cause__, PageLimitExceededError)
            ):
                # HTTPException wraps the original PageLimitExceededError
                page_limit_error = e.__cause__
            elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
                # Fallback: HTTPException with page limit message but no cause
                page_limit_error = None  # We don't have the details

            # For page limit errors, create a dedicated page_limit_exceeded notification
            if page_limit_error is not None:
                error_message = str(page_limit_error)
                # Create a dedicated page limit exceeded notification
                try:
                    # First, mark the processing notification as failed
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Page limit exceeded",
                    )

                    # Then create a separate page_limit_exceeded notification for better UX
                    await NotificationService.page_limit.notify_page_limit_exceeded(
                        session=session,
                        user_id=UUID(user_id),
                        document_name=filename,
                        document_type="FILE",
                        search_space_id=search_space_id,
                        pages_used=page_limit_error.pages_used,
                        pages_limit=page_limit_error.pages_limit,
                        pages_to_add=page_limit_error.pages_to_add,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to create page limit notification: {notif_error!s}"
                    )
            elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
                # HTTPException with page limit message but no detailed cause
                error_message = str(e.detail)
                try:
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=error_message,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )
            else:
                error_message = str(e)[:100]
                # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
                try:
                    # Refresh notification to ensure it's not stale after any rollback
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=error_message,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )

            await task_logger.log_task_failure(
                log_entry,
                error_message,
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(error_message)
            raise
        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            heartbeat_task.cancel()
            _stop_heartbeat(notification.id)


@celery_app.task(name="process_file_upload_with_document", bind=True)
def process_file_upload_with_document_task(
    self,
    document_id: int,
    temp_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    should_summarize: bool = False,
):
    """
    Celery task to process uploaded file with existing pending document.

    This task is used by the 2-phase document upload flow:
    - Phase 1 (API): Creates pending document (visible in UI immediately)
    - Phase 2 (this task): Updates document status: pending → processing → ready/failed

    Args:
        document_id: ID of the pending document created in Phase 1
        temp_path: Path to the uploaded file
        filename: Original filename
        search_space_id: ID of the search space
        user_id: ID of the user
        should_summarize: Whether to generate an LLM summary
    """
    import traceback

    logger.info(
        f"[process_file_upload_with_document] Task started - document_id: {document_id}, "
        f"file: {filename}, search_space_id: {search_space_id}"
    )

    # Check if file exists and is accessible
    if not os.path.exists(temp_path):
        logger.error(
            f"[process_file_upload_with_document] File does not exist: {temp_path}. "
            "File may have been removed before syncing could start."
        )
        # Mark document as failed since file is missing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _mark_document_failed(
                    document_id,
                    "File not found. Please re-upload the file.",
                )
            )
        finally:
            loop.close()
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_file_with_document(
                document_id,
                temp_path,
                filename,
                search_space_id,
                user_id,
                should_summarize=should_summarize,
            )
        )
        logger.info(
            f"[process_file_upload_with_document] Task completed successfully for: {filename}"
        )
    except Exception as e:
        logger.error(
            f"[process_file_upload_with_document] Task failed for {filename}: {e}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        raise
    finally:
        loop.close()


async def _mark_document_failed(document_id: int, reason: str):
    """Mark a document as failed when task cannot proceed."""
    from app.db import Document, DocumentStatus
    from app.tasks.document_processors.base import get_current_timestamp

    async with get_celery_session_maker()() as session:
        document = await session.get(Document, document_id)
        if document:
            document.status = DocumentStatus.failed(reason)
            document.updated_at = get_current_timestamp()
            await session.commit()
            logger.info(f"Marked document {document_id} as failed: {reason}")


async def _process_file_with_document(
    document_id: int,
    temp_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    should_summarize: bool = False,
):
    """
    Process file and update existing pending document status.

    This function implements Phase 2 of the 2-phase document upload:
    - Sets document status to 'processing' (shows spinner in UI)
    - Processes the file (parsing, embedding, chunking)
    - Updates document to 'ready' on success or 'failed' on error
    """
    from app.db import Document, DocumentStatus
    from app.tasks.document_processors.base import get_current_timestamp
    from app.tasks.document_processors.file_processors import (
        process_file_in_background_with_document,
    )

    logger.info(
        f"[_process_file_with_document] Starting async processing for: {filename}"
    )

    async with get_celery_session_maker()() as session:
        logger.info(
            f"[_process_file_with_document] Database session created for: {filename}"
        )
        task_logger = TaskLoggingService(session, search_space_id)

        # Get the document
        document = await session.get(Document, document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        # Get file size for notification metadata
        try:
            file_size = os.path.getsize(temp_path)
            logger.info(f"[_process_file_with_document] File size: {file_size} bytes")
        except Exception as e:
            logger.warning(
                f"[_process_file_with_document] Could not get file size: {e}"
            )
            file_size = None

        # Create notification for document processing
        logger.info(
            f"[_process_file_with_document] Creating notification for: {filename}"
        )
        notification = (
            await NotificationService.document_processing.notify_processing_started(
                session=session,
                user_id=UUID(user_id),
                document_type="FILE",
                document_name=filename,
                search_space_id=search_space_id,
                file_size=file_size,
            )
        )

        # Store document_id in notification metadata so cleanup task can find the document
        if notification and notification.notification_metadata is not None:
            notification.notification_metadata["document_id"] = document_id
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(notification, "notification_metadata")
            await session.commit()
            await session.refresh(notification)

        # Start Redis heartbeat for stale task detection
        _start_heartbeat(notification.id)
        heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))

        log_entry = await task_logger.log_task_start(
            task_name="process_file_upload_with_document",
            source="document_processor",
            message=f"Starting file processing for: {filename} (document_id: {document_id})",
            metadata={
                "document_type": "FILE",
                "document_id": document_id,
                "filename": filename,
                "file_path": temp_path,
                "user_id": user_id,
            },
        )

        try:
            # Set status to PROCESSING (shows spinner in UI via ElectricSQL)
            document.status = DocumentStatus.processing()
            await session.commit()
            logger.info(
                f"[_process_file_with_document] Document {document_id} status set to 'processing'"
            )

            # Process the file and update document
            result = await process_file_in_background_with_document(
                document=document,
                file_path=temp_path,
                filename=filename,
                search_space_id=search_space_id,
                user_id=user_id,
                session=session,
                task_logger=task_logger,
                log_entry=log_entry,
                notification=notification,
                should_summarize=should_summarize,
            )

            # Update notification on success
            if result:
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                )
                logger.info(
                    f"[_process_file_with_document] Successfully processed document {document_id}"
                )
            else:
                # Duplicate detected - mark as failed
                document.status = DocumentStatus.failed("Duplicate content detected")
                document.updated_at = get_current_timestamp()
                await session.commit()
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Document already exists (duplicate)",
                    )
                )

        except Exception as e:
            # Import here to avoid circular dependencies
            from fastapi import HTTPException

            from app.services.page_limit_service import PageLimitExceededError

            # Check if this is a page limit error
            page_limit_error: PageLimitExceededError | None = None
            if isinstance(e, PageLimitExceededError):
                page_limit_error = e
            elif (
                isinstance(e, HTTPException)
                and e.__cause__
                and isinstance(e.__cause__, PageLimitExceededError)
            ):
                page_limit_error = e.__cause__

            # Mark document as failed (shows error in UI via ElectricSQL)
            error_message = str(e)[:500]
            document.status = DocumentStatus.failed(error_message)
            document.updated_at = get_current_timestamp()
            await session.commit()
            logger.info(
                f"[_process_file_with_document] Document {document_id} marked as failed: {error_message[:100]}"
            )

            # Handle page limit errors with dedicated notification
            if page_limit_error is not None:
                try:
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Page limit exceeded",
                    )
                    await NotificationService.page_limit.notify_page_limit_exceeded(
                        session=session,
                        user_id=UUID(user_id),
                        document_name=filename,
                        document_type="FILE",
                        search_space_id=search_space_id,
                        pages_used=page_limit_error.pages_used,
                        pages_limit=page_limit_error.pages_limit,
                        pages_to_add=page_limit_error.pages_to_add,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to create page limit notification: {notif_error!s}"
                    )
            else:
                # Update notification on failure
                try:
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )

            await task_logger.log_task_failure(
                log_entry,
                error_message[:100],
                str(e),
                {"error_type": type(e).__name__, "document_id": document_id},
            )
            logger.error(f"Error processing file {filename}: {e!s}")
            raise

        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            heartbeat_task.cancel()
            _stop_heartbeat(notification.id)

            # Clean up temp file
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.info(
                        f"[_process_file_with_document] Cleaned up temp file: {temp_path}"
                    )
                except Exception as cleanup_error:
                    logger.warning(
                        f"[_process_file_with_document] Failed to clean up temp file: {cleanup_error}"
                    )


@celery_app.task(name="process_circleback_meeting", bind=True)
def process_circleback_meeting_task(
    self,
    meeting_id: int,
    meeting_name: str,
    markdown_content: str,
    metadata: dict,
    search_space_id: int,
    connector_id: int | None = None,
):
    """
    Celery task to process Circleback meeting webhook data.

    Args:
        meeting_id: Circleback meeting ID
        meeting_name: Name of the meeting
        markdown_content: Meeting content formatted as markdown
        metadata: Meeting metadata dictionary
        search_space_id: ID of the search space
        connector_id: ID of the Circleback connector (for deletion support)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_circleback_meeting(
                meeting_id,
                meeting_name,
                markdown_content,
                metadata,
                search_space_id,
                connector_id,
            )
        )
    finally:
        loop.close()


async def _process_circleback_meeting(
    meeting_id: int,
    meeting_name: str,
    markdown_content: str,
    metadata: dict,
    search_space_id: int,
    connector_id: int | None = None,
):
    """Process Circleback meeting with new session."""
    from app.tasks.document_processors.circleback_processor import (
        add_circleback_meeting_document,
    )

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

        # Get user_id from metadata if available
        user_id = metadata.get("user_id")

        # Create notification if user_id is available
        notification = None
        heartbeat_task = None
        if user_id:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="CIRCLEBACK",
                    document_name=f"Meeting: {meeting_name[:40]}",
                    search_space_id=search_space_id,
                )
            )

            # Start Redis heartbeat for stale task detection
            _start_heartbeat(notification.id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))

        log_entry = await task_logger.log_task_start(
            task_name="process_circleback_meeting",
            source="circleback_webhook",
            message=f"Starting Circleback meeting processing: {meeting_name}",
            metadata={
                "document_type": "CIRCLEBACK",
                "meeting_id": meeting_id,
                "meeting_name": meeting_name,
                **metadata,
            },
        )

        try:
            # Update notification: parsing stage
            if notification:
                await (
                    NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Reading meeting notes",
                    )
                )

            result = await add_circleback_meeting_document(
                session=session,
                meeting_id=meeting_id,
                meeting_name=meeting_name,
                markdown_content=markdown_content,
                metadata=metadata,
                search_space_id=search_space_id,
                connector_id=connector_id,
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed Circleback meeting: {meeting_name}",
                    {
                        "document_id": result.id,
                        "meeting_id": meeting_id,
                        "content_hash": result.content_hash,
                    },
                )

                # Update notification on success
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Circleback meeting document already exists (duplicate): {meeting_name}",
                    {"duplicate_detected": True, "meeting_id": meeting_id},
                )

                # Update notification for duplicate
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Meeting already saved (duplicate)",
                    )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process Circleback meeting: {meeting_name}",
                str(e),
                {"error_type": type(e).__name__, "meeting_id": meeting_id},
            )

            # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
            if notification:
                try:
                    # Refresh notification to ensure it's not stale after any rollback
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )

            logger.error(f"Error processing Circleback meeting: {e!s}")
            raise
        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification:
                _stop_heartbeat(notification.id)
