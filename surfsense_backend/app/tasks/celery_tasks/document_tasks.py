"""Celery tasks for document processing."""

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.services.task_logging_service import TaskLoggingService
from app.tasks.document_processors import (
    add_crawled_url_document,
    add_extension_received_document,
    add_youtube_video_document,
)

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    This is necessary because Celery tasks run in a new event loop,
    and the default session maker is bound to the main app's event loop.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,  # Don't use connection pooling for Celery tasks
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


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
    import asyncio

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
    from pydantic import BaseModel

    # Reconstruct the document object from dict
    # You'll need to define the proper model for this
    class DocumentMetadata(BaseModel):
        VisitedWebPageTitle: str
        VisitedWebPageURL: str

    class IndividualDocument(BaseModel):
        metadata: DocumentMetadata
        content: str

    individual_document = IndividualDocument(**individual_document_dict)

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

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
            result = await add_extension_received_document(
                session, individual_document, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed extension document: {individual_document.metadata.VisitedWebPageTitle}",
                    {"document_id": result.id, "content_hash": result.content_hash},
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Extension document already exists (duplicate): {individual_document.metadata.VisitedWebPageTitle}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process extension document: {individual_document.metadata.VisitedWebPageTitle}",
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(f"Error processing extension document: {e!s}")
            raise


@celery_app.task(name="process_crawled_url", bind=True)
def process_crawled_url_task(self, url: str, search_space_id: int, user_id: str):
    """
    Celery task to process crawled URL.

    Args:
        url: URL to crawl and process
        search_space_id: ID of the search space
        user_id: ID of the user
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_process_crawled_url(url, search_space_id, user_id))
    finally:
        loop.close()


async def _process_crawled_url(url: str, search_space_id: int, user_id: str):
    """Process crawled URL with new session."""
    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

        log_entry = await task_logger.log_task_start(
            task_name="process_crawled_url",
            source="document_processor",
            message=f"Starting URL crawling and processing for: {url}",
            metadata={"document_type": "CRAWLED_URL", "url": url, "user_id": user_id},
        )

        try:
            result = await add_crawled_url_document(
                session, url, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully crawled and processed URL: {url}",
                    {
                        "document_id": result.id,
                        "title": result.title,
                        "content_hash": result.content_hash,
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"URL document already exists (duplicate): {url}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to crawl URL: {url}",
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(f"Error processing crawled URL: {e!s}")
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
    import asyncio

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

        log_entry = await task_logger.log_task_start(
            task_name="process_youtube_video",
            source="document_processor",
            message=f"Starting YouTube video processing for: {url}",
            metadata={"document_type": "YOUTUBE_VIDEO", "url": url, "user_id": user_id},
        )

        try:
            result = await add_youtube_video_document(
                session, url, search_space_id, user_id
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
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"YouTube video document already exists (duplicate): {url}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process YouTube video: {url}",
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(f"Error processing YouTube video: {e!s}")
            raise


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
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_file_upload(file_path, filename, search_space_id, user_id)
        )
    finally:
        loop.close()


async def _process_file_upload(
    file_path: str, filename: str, search_space_id: int, user_id: str
):
    """Process file upload with new session."""
    from app.tasks.document_processors.file_processors import process_file_in_background

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

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
            await process_file_in_background(
                file_path,
                filename,
                search_space_id,
                user_id,
                session,
                task_logger,
                log_entry,
            )
        except Exception as e:
            # Import here to avoid circular dependencies
            from fastapi import HTTPException

            from app.services.page_limit_service import PageLimitExceededError

            # For page limit errors, use the detailed message from the exception
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
                {"error_type": type(e).__name__},
            )
            logger.error(error_message)
            raise
