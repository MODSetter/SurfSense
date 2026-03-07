"""
Notion connector indexer.

Implements real-time document status updates using a two-phase approach:
- Phase 1: Create all documents with PENDING status (visible in UI immediately)
- Phase 2: Process each document one by one (pending → processing → ready/failed)
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
from app.utils.notion_utils import process_blocks

from .base import (
    build_document_metadata_string,
    calculate_date_range,
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    safe_set_chunks,
    update_connector_last_indexed,
)

# Type alias for retry callback
# Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds) -> None
RetryCallbackType = Callable[[str, int, int, float], Awaitable[None]]

# Type alias for heartbeat callback
# Signature: async callback(indexed_count) -> None
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds - update notification every 30 seconds
HEARTBEAT_INTERVAL_SECONDS = 30


async def index_notion_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_retry_callback: RetryCallbackType | None = None,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index Notion pages from all accessible pages.

    Args:
        session: Database session
        connector_id: ID of the Notion connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_retry_callback: Optional callback for retry progress notifications.
            Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds)
            retry_reason is one of: 'rate_limit', 'server_error', 'timeout'
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.
            Called periodically with (indexed_count) to prevent task appearing stuck.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="notion_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Notion pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Notion connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.NOTION_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
            )

        # Check if access_token exists (support both new OAuth format and old integration token format)
        if not connector.config.get("access_token") and not connector.config.get(
            "NOTION_INTEGRATION_TOKEN"
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"Notion access token not found in connector config for connector {connector_id}",
                "Missing Notion access token",
                {"error_type": "MissingToken"},
            )
            return 0, "Notion access token not found in connector config"

        # Initialize Notion client with internal refresh capability
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Notion client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        logger.info(f"Initializing Notion client for connector {connector_id}")

        # Handle 'undefined' string from frontend (treat as None)
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range using the shared utility function
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        # Convert YYYY-MM-DD to ISO format for Notion API
        start_date_iso = datetime.strptime(start_date_str, "%Y-%m-%d").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        end_date_iso = datetime.strptime(end_date_str, "%Y-%m-%d").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # Create connector with session and connector_id for internal refresh
        # Token refresh will happen automatically when needed
        notion_client = NotionHistoryConnector(
            session=session, connector_id=connector_id
        )

        # Set retry callback if provided (for user notifications during rate limits)
        if on_retry_callback:
            notion_client.set_retry_callback(on_retry_callback)

        logger.info(f"Fetching Notion pages from {start_date_iso} to {end_date_iso}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Notion pages from {start_date_iso} to {end_date_iso}",
            {
                "stage": "fetch_pages",
                "start_date": start_date_iso,
                "end_date": end_date_iso,
            },
        )

        # Get all pages
        try:
            pages = await notion_client.get_all_pages(
                start_date=start_date_iso, end_date=end_date_iso
            )
            logger.info(f"Found {len(pages)} Notion pages")

            # Get count of pages that had unsupported content skipped
            pages_with_skipped_content = notion_client.get_skipped_content_count()
            if pages_with_skipped_content > 0:
                logger.info(
                    f"{pages_with_skipped_content} pages had Notion AI content skipped (not available via API)"
                )

            # Check if using legacy integration token and log warning
            if notion_client.is_using_legacy_token():
                logger.warning(
                    f"Connector {connector_id} is using legacy integration token. "
                    "Recommend reconnecting with OAuth."
                )
        except Exception as e:
            error_str = str(e)
            # Check if this is an unsupported block type error (transcription, ai_block, etc.)
            # These are known Notion API limitations and should be logged as warnings, not errors
            unsupported_block_errors = [
                "transcription is not supported",
                "ai_block is not supported",
                "is not supported via the API",
            ]
            is_unsupported_block_error = any(
                err in error_str.lower() for err in unsupported_block_errors
            )

            if is_unsupported_block_error:
                # Log as warning since this is a known Notion API limitation
                logger.warning(
                    f"Notion API limitation for connector {connector_id}: {error_str}. "
                    "This is a known issue with Notion AI blocks (transcription, ai_block) "
                    "that are not accessible via the Notion API."
                )
                await task_logger.log_task_failure(
                    log_entry,
                    "Failed to get Notion pages: Notion API limitation",
                    f"{error_str} - This page contains Notion AI content (transcription/ai_block) that cannot be accessed via the API.",
                    {"error_type": "UnsupportedBlockType", "is_known_limitation": True},
                )
            else:
                # Log as error for other failures
                logger.error(
                    f"Error fetching Notion pages for connector {connector_id}: {error_str}",
                    exc_info=True,
                )
                await task_logger.log_task_failure(
                    log_entry,
                    f"Failed to get Notion pages for connector {connector_id}",
                    str(e),
                    {"error_type": "PageFetchError"},
                )

            await notion_client.close()
            return 0, f"Failed to get Notion pages: {e!s}"

        if not pages:
            await task_logger.log_task_success(
                log_entry,
                f"No Notion pages found for connector {connector_id}. "
                "Ensure pages are shared with the Notion integration.",
                {"pages_found": 0},
            )
            logger.info("No Notion pages found to index")
            # CRITICAL: Update timestamp even when no pages found so Electric SQL syncs
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            await notion_client.close()
            return 0, None  # Success with 0 pages, not an error

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0
        duplicate_content_count = 0
        skipped_pages = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(pages)} Notion pages",
            {"stage": "process_pages", "total_pages": len(pages)},
        )

        # =======================================================================
        # PHASE 1: Analyze all pages, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        pages_to_process = []  # List of dicts with document and page data
        new_documents_created = False

        for page in pages:
            try:
                page_id = page.get("page_id")
                page_title = page.get("title", f"Untitled page ({page_id})")
                page_content = page.get("content", [])

                if not page_id:
                    documents_skipped += 1
                    continue

                if not page_content:
                    logger.info(f"No content found in page {page_title}. Skipping.")
                    skipped_pages.append(f"{page_title} (no content)")
                    documents_skipped += 1
                    continue

                # Convert page content to markdown format
                markdown_content = f"# Notion Page: {page_title}\n\n"
                markdown_content += process_blocks(page_content)

                # Format document metadata
                metadata_sections = [
                    ("METADATA", [f"PAGE_TITLE: {page_title}", f"PAGE_ID: {page_id}"]),
                    (
                        "CONTENT",
                        [
                            "FORMAT: markdown",
                            "TEXT_START",
                            markdown_content,
                            "TEXT_END",
                        ],
                    ),
                ]

                # Build the document string
                combined_document_string = build_document_metadata_string(
                    metadata_sections
                )

                # Generate unique identifier hash for this Notion page
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.NOTION_CONNECTOR, page_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(
                    combined_document_string, search_space_id
                )

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        # Ensure status is ready (might have been stuck in processing/pending)
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        documents_skipped += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    pages_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "markdown_content": markdown_content,
                            "content_hash": content_hash,
                            "page_id": page_id,
                            "page_title": page_title,
                        }
                    )
                    continue

                # Document doesn't exist by unique_identifier_hash
                # Check if a document with the same content_hash exists (from another connector)
                with session.no_autoflush:
                    duplicate_by_content = await check_duplicate_document_by_hash(
                        session, content_hash
                    )

                if duplicate_by_content:
                    logger.info(
                        f"Notion page {page_title} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=page_title,
                    document_type=DocumentType.NOTION_CONNECTOR,
                    document_metadata={
                        "page_title": page_title,
                        "page_id": page_id,
                        "connector_id": connector_id,
                    },
                    content="Pending...",  # Placeholder until processed
                    content_hash=unique_identifier_hash,  # Temporary unique value - updated when ready
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=None,
                    chunks=[],  # Empty at creation - safe for async
                    status=DocumentStatus.pending(),  # Pending until processing starts
                    updated_at=get_current_timestamp(),
                    created_by_id=user_id,
                    connector_id=connector_id,
                )
                session.add(document)
                new_documents_created = True

                pages_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "markdown_content": markdown_content,
                        "content_hash": content_hash,
                        "page_id": page_id,
                        "page_title": page_title,
                    }
                )

            except Exception as e:
                logger.error(f"Error in Phase 1 for page: {e!s}", exc_info=True)
                documents_failed += 1
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([p for p in pages_to_process if p['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(pages_to_process)} documents")

        for item in pages_to_process:
            # Send heartbeat periodically
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(documents_indexed)
                    last_heartbeat_time = current_time

            document = item["document"]
            try:
                # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                document.status = DocumentStatus.processing()
                await session.commit()

                # Heavy processing (LLM, embeddings, chunks)
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm and connector.enable_summary:
                    document_metadata_for_summary = {
                        "page_title": item["page_title"],
                        "page_id": item["page_id"],
                        "document_type": "Notion Page",
                        "connector_type": "Notion",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        item["markdown_content"],
                        user_llm,
                        document_metadata_for_summary,
                    )
                else:
                    summary_content = f"Notion Page: {item['page_title']}\n\n{item['markdown_content']}"
                    summary_embedding = embed_text(summary_content)

                chunks = await create_document_chunks(item["markdown_content"])

                # Update document to READY with actual content
                document.title = item["page_title"]
                document.content = summary_content
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = {
                    "page_title": item["page_title"],
                    "page_id": item["page_id"],
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "connector_id": connector_id,
                }
                safe_set_chunks(document, chunks)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                documents_indexed += 1

                # Batch commit every 10 documents (for ready status updates)
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Notion pages processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Notion page: {e!s}", exc_info=True)
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(e))
                    document.updated_at = get_current_timestamp()
                except Exception as status_error:
                    logger.error(
                        f"Failed to update document status to failed: {status_error}"
                    )
                skipped_pages.append(f"{item['page_title']} (processing error)")
                documents_failed += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        total_processed = documents_indexed

        # Final commit to ensure all documents are persisted (safety net)
        logger.info(f"Final commit: Total {documents_indexed} documents processed")
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Notion document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same page was indexed by multiple connectors. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
                # Don't fail the entire task - some documents may have been successfully indexed
            else:
                raise

        # Get final count of pages with skipped Notion AI content
        pages_with_skipped_ai_content = notion_client.get_skipped_content_count()

        # Build warning message if there were issues
        warning_parts = []
        if duplicate_content_count > 0:
            warning_parts.append(f"{duplicate_content_count} duplicate")
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        # Prepare result message with user-friendly notification about skipped content
        result_message = None
        if skipped_pages:
            result_message = f"Processed {total_processed} pages. Skipped {len(skipped_pages)} pages: {', '.join(skipped_pages)}"
        else:
            result_message = f"Processed {total_processed} pages."

        # Add user-friendly message about skipped Notion AI content
        if pages_with_skipped_ai_content > 0:
            result_message += (
                " Audio transcriptions and AI summaries from Notion aren't accessible "
                "via their API - all other content was saved."
            )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Notion indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
                "skipped_pages_count": len(skipped_pages),
                "pages_with_skipped_ai_content": pages_with_skipped_ai_content,
                "result_message": result_message,
            },
        )

        logger.info(
            f"Notion indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )

        # Clean up the async client
        await notion_client.close()

        # Build user-friendly notification messages
        # This will be shown in the notification to inform users
        notification_parts = []

        if pages_with_skipped_ai_content > 0:
            notification_parts.append(
                "Some Notion AI content couldn't be synced (API limitation)"
            )

        if notion_client.is_using_legacy_token():
            notification_parts.append(
                "Using legacy token. Reconnect with OAuth for better reliability."
            )

        # Include warning message if there were issues
        if warning_message:
            notification_parts.append(warning_message)

        user_notification_message = (
            " ".join(notification_parts) if notification_parts else None
        )

        return (
            total_processed,
            user_notification_message,
        )

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Notion indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Notion indexing: {db_error!s}", exc_info=True
        )
        # Clean up the async client in case of error
        if "notion_client" in locals():
            await notion_client.close()
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Notion pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Notion pages: {e!s}", exc_info=True)
        # Clean up the async client in case of error
        if "notion_client" in locals():
            await notion_client.close()
        return 0, f"Failed to index Notion pages: {e!s}"
