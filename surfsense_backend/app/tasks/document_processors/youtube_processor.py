"""
YouTube video document processor.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Create document with 'pending' status (visible in UI immediately)
- Phase 2: Process document: pending → processing → ready/failed
"""

import logging
from urllib.parse import parse_qs, urlparse

import aiohttp
from fake_useragent import UserAgent
from requests import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import YouTubeTranscriptApi

from app.db import Document, DocumentStatus, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
from app.utils.proxy_config import get_requests_proxies

from .base import (
    check_document_by_unique_identifier,
    get_current_timestamp,
    safe_set_chunks,
)


def get_youtube_video_id(url: str) -> str | None:
    """
    Extract video ID from various YouTube URL formats.

    Args:
        url: YouTube URL

    Returns:
        Video ID if found, None otherwise
    """
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname

    if hostname == "youtu.be":
        return parsed_url.path[1:]
    if hostname in ("www.youtube.com", "youtube.com"):
        if parsed_url.path == "/watch":
            query_params = parse_qs(parsed_url.query)
            return query_params.get("v", [None])[0]
        if parsed_url.path.startswith("/embed/"):
            return parsed_url.path.split("/")[2]
        if parsed_url.path.startswith("/v/"):
            return parsed_url.path.split("/")[2]
    return None


async def add_youtube_video_document(
    session: AsyncSession,
    url: str,
    search_space_id: int,
    user_id: str,
    notification=None,
) -> Document:
    """
    Process a YouTube video URL, extract transcripts, and store as a document.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create document with 'pending' status (visible in UI immediately)
    - Phase 2: Process document: pending → processing → ready/failed

    Args:
        session: Database session for storing the document
        url: YouTube video URL (supports standard, shortened, and embed formats)
        search_space_id: ID of the search space to add the document to
        user_id: ID of the user
        notification: Optional notification object — if provided, the document_id
            is stored in its metadata right after document creation so the stale
            cleanup task can identify stuck documents.

    Returns:
        Document: The created document object

    Raises:
        ValueError: If the YouTube video ID cannot be extracted from the URL
        SQLAlchemyError: If there's a database error
        RuntimeError: If the video processing fails
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="youtube_video_document",
        source="background_task",
        message=f"Starting YouTube video processing for: {url}",
        metadata={"url": url, "user_id": str(user_id)},
    )

    document = None
    video_id = None
    is_new_document = False

    try:
        # Extract video ID from URL (lightweight operation)
        await task_logger.log_task_progress(
            log_entry,
            f"Extracting video ID from URL: {url}",
            {"stage": "video_id_extraction"},
        )

        video_id = get_youtube_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        await task_logger.log_task_progress(
            log_entry,
            f"Video ID extracted: {video_id}",
            {"stage": "video_id_extracted", "video_id": video_id},
        )

        # Generate unique identifier hash for this YouTube video
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.YOUTUBE_VIDEO, video_id, search_space_id
        )

        # Check if document with this unique identifier already exists
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for existing video: {video_id}",
            {"stage": "duplicate_check", "video_id": video_id},
        )

        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        # =======================================================================
        # PHASE 1: Create pending document or prepare existing for update
        # =======================================================================
        if existing_document:
            document = existing_document
            is_new_document = False
            # Check if already being processed
            if DocumentStatus.is_state(
                existing_document.status, DocumentStatus.PENDING
            ):
                logging.info(
                    f"YouTube video {video_id} already pending. Returning existing."
                )
                return existing_document
            if DocumentStatus.is_state(
                existing_document.status, DocumentStatus.PROCESSING
            ):
                logging.info(
                    f"YouTube video {video_id} already processing. Returning existing."
                )
                return existing_document
        else:
            # Create new document with PENDING status (visible in UI immediately)
            await task_logger.log_task_progress(
                log_entry,
                f"Creating pending document for video: {video_id}",
                {"stage": "pending_document_creation"},
            )

            document = Document(
                title=f"YouTube Video: {video_id}",  # Placeholder title
                document_type=DocumentType.YOUTUBE_VIDEO,
                document_metadata={
                    "url": url,
                    "video_id": video_id,
                },
                content="Processing video...",  # Placeholder content
                content_hash=unique_identifier_hash,  # Temporary unique value
                unique_identifier_hash=unique_identifier_hash,
                embedding=None,
                chunks=[],  # Empty at creation
                status=DocumentStatus.pending(),  # PENDING status - visible in UI
                search_space_id=search_space_id,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )
            session.add(document)
            await session.commit()  # Document visible in UI now with pending status!
            is_new_document = True

            # Store document_id in notification metadata so stale cleanup task
            # can identify this document if the worker crashes.
            if notification and notification.notification_metadata is not None:
                from sqlalchemy.orm.attributes import flag_modified

                notification.notification_metadata["document_id"] = document.id
                flag_modified(notification, "notification_metadata")
                await session.commit()

            logging.info(f"Created pending document for YouTube video {video_id}")

        # =======================================================================
        # PHASE 2: Set to PROCESSING and do heavy work
        # =======================================================================
        document.status = DocumentStatus.processing()
        await session.commit()  # UI shows "processing" status

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching video metadata for: {video_id}",
            {"stage": "metadata_fetch"},
        )

        # Fetch video metadata
        params = {
            "format": "json",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        oembed_url = "https://www.youtube.com/oembed"

        # Build residential proxy URL (if configured)
        residential_proxies = get_requests_proxies()

        async with (
            aiohttp.ClientSession() as http_session,
            http_session.get(
                oembed_url,
                params=params,
                proxy=residential_proxies["http"] if residential_proxies else None,
            ) as response,
        ):
            video_data = await response.json()

        # Update title immediately for better UX (user sees actual title sooner)
        document.title = video_data.get("title", f"YouTube Video: {video_id}")
        await session.commit()

        await task_logger.log_task_progress(
            log_entry,
            f"Video metadata fetched: {video_data.get('title', 'Unknown')}",
            {
                "stage": "metadata_fetched",
                "title": video_data.get("title"),
                "author": video_data.get("author_name"),
            },
        )

        # Get video transcript
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching transcript for video: {video_id}",
            {"stage": "transcript_fetch"},
        )

        try:
            ua = UserAgent()
            http_client = Session()
            http_client.headers.update({"User-Agent": ua.random})
            if residential_proxies:
                http_client.proxies.update(residential_proxies)
            ytt_api = YouTubeTranscriptApi(http_client=http_client)

            # List all available transcripts and pick the first one
            # (the video's primary language) instead of defaulting to English
            transcript_list = ytt_api.list(video_id)
            transcript = next(iter(transcript_list))
            captions = transcript.fetch()

            # Include complete caption information with timestamps
            transcript_segments = []
            for line in captions:
                start_time = line.start
                duration = line.duration
                text = line.text
                timestamp = f"[{start_time:.2f}s-{start_time + duration:.2f}s]"
                transcript_segments.append(f"{timestamp} {text}")
            transcript_text = "\n".join(transcript_segments)

            await task_logger.log_task_progress(
                log_entry,
                f"Transcript fetched successfully: {len(captions)} segments ({transcript.language})",
                {
                    "stage": "transcript_fetched",
                    "segments_count": len(captions),
                    "transcript_length": len(transcript_text),
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                },
            )
        except Exception as e:
            transcript_text = f"No captions available for this video. Error: {e!s}"
            await task_logger.log_task_progress(
                log_entry,
                f"No transcript available for video: {video_id}",
                {"stage": "transcript_unavailable", "error": str(e)},
            )

        # Format document
        await task_logger.log_task_progress(
            log_entry,
            f"Processing video content: {video_data.get('title', 'YouTube Video')}",
            {"stage": "content_processing"},
        )

        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"TITLE: {video_data.get('title', 'YouTube Video')}",
                    f"URL: {url}",
                    f"VIDEO_ID: {video_id}",
                    f"AUTHOR: {video_data.get('author_name', 'Unknown')}",
                    f"THUMBNAIL: {video_data.get('thumbnail_url', '')}",
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: transcript", "TEXT_START", transcript_text, "TEXT_END"],
            ),
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = "\n".join(document_parts)

        # Generate content hash
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # For existing documents, check if content has changed
        if not is_new_document and existing_document.content_hash == content_hash:
            await task_logger.log_task_success(
                log_entry,
                f"YouTube video document unchanged: {video_data.get('title', 'YouTube Video')}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                    "video_id": video_id,
                },
            )
            logging.info(
                f"Document for YouTube video {video_id} unchanged. Marking as ready."
            )
            document.status = DocumentStatus.ready()
            await session.commit()
            return document

        # Get LLM for summary generation
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {video_data.get('title', 'YouTube Video')}",
            {"stage": "llm_setup"},
        )

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary
        await task_logger.log_task_progress(
            log_entry,
            f"Generating summary for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "summary_generation"},
        )

        # Generate summary with metadata
        document_metadata_for_summary = {
            "url": url,
            "video_id": video_id,
            "title": video_data.get("title", "YouTube Video"),
            "author": video_data.get("author_name", "Unknown"),
            "thumbnail": video_data.get("thumbnail_url", ""),
            "document_type": "YouTube Video Document",
            "has_transcript": "No captions available" not in transcript_text,
        }
        summary_content, summary_embedding = await generate_document_summary(
            combined_document_string, user_llm, document_metadata_for_summary
        )

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "chunk_processing"},
        )

        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        # Convert transcript to BlockNote JSON
        blocknote_json = await convert_markdown_to_blocknote(combined_document_string)
        if not blocknote_json:
            logging.warning(
                f"Failed to convert YouTube video '{video_id}' to BlockNote JSON, "
                "document will not be editable"
            )

        chunks = await create_document_chunks(combined_document_string)

        # =======================================================================
        # PHASE 3: Update document to READY with all content
        # =======================================================================
        await task_logger.log_task_progress(
            log_entry,
            f"Finalizing document: {video_data.get('title', 'YouTube Video')}",
            {"stage": "document_finalization", "chunks_count": len(chunks)},
        )

        document.title = video_data.get("title", "YouTube Video")
        document.content = summary_content
        document.content_hash = content_hash
        document.embedding = summary_embedding
        document.document_metadata = {
            "url": url,
            "video_id": video_id,
            "video_title": video_data.get("title", "YouTube Video"),
            "author": video_data.get("author_name", "Unknown"),
            "thumbnail": video_data.get("thumbnail_url", ""),
        }
        safe_set_chunks(document, chunks)
        document.blocknote_document = blocknote_json
        document.status = DocumentStatus.ready()  # READY status - fully processed
        document.updated_at = get_current_timestamp()

        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed YouTube video: {video_data.get('title', 'YouTube Video')}",
            {
                "document_id": document.id,
                "video_id": video_id,
                "title": document.title,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
                "has_transcript": "No captions available" not in transcript_text,
            },
        )

        return document

    except SQLAlchemyError as db_error:
        # Mark document as failed if it exists
        if document:
            try:
                document.status = DocumentStatus.failed(
                    f"Database error: {str(db_error)[:150]}"
                )
                document.updated_at = get_current_timestamp()
                await session.commit()
            except Exception:
                await session.rollback()
        else:
            await session.rollback()

        await task_logger.log_task_failure(
            log_entry,
            f"Database error while processing YouTube video: {url}",
            str(db_error),
            {
                "error_type": "SQLAlchemyError",
                "video_id": video_id,
            },
        )
        raise db_error

    except Exception as e:
        # Mark document as failed if it exists
        if document:
            try:
                document.status = DocumentStatus.failed(str(e)[:200])
                document.updated_at = get_current_timestamp()
                await session.commit()
            except Exception:
                await session.rollback()
        else:
            await session.rollback()

        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process YouTube video: {url}",
            str(e),
            {
                "error_type": type(e).__name__,
                "video_id": video_id,
            },
        )
        logging.error(f"Failed to process YouTube video: {e!s}")
        raise
