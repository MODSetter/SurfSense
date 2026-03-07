"""
BookStack connector indexer.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Collect all pages and create pending documents (visible in UI immediately)
- Phase 2: Process each page: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.bookstack_connector import BookStackConnector
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

from .base import (
    calculate_date_range,
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    safe_set_chunks,
    update_connector_last_indexed,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 30


async def index_bookstack_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index BookStack pages.

    Args:
        session: Database session
        connector_id: ID of the BookStack connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="bookstack_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting BookStack pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.BOOKSTACK_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the BookStack credentials from the connector config
        bookstack_base_url = connector.config.get("BOOKSTACK_BASE_URL")
        bookstack_token_id = connector.config.get("BOOKSTACK_TOKEN_ID")
        bookstack_token_secret = connector.config.get("BOOKSTACK_TOKEN_SECRET")

        if (
            not bookstack_base_url
            or not bookstack_token_id
            or not bookstack_token_secret
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"BookStack credentials not found in connector config for connector {connector_id}",
                "Missing BookStack credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "BookStack credentials not found in connector config"

        # Initialize BookStack client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing BookStack client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        bookstack_client = BookStackConnector(
            base_url=bookstack_base_url,
            token_id=bookstack_token_id,
            token_secret=bookstack_token_secret,
        )

        # Calculate date range
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching BookStack pages from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_pages",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get pages within date range
        try:
            pages, error = bookstack_client.get_pages_by_date_range(
                start_date=start_date_str, end_date=end_date_str
            )

            if error:
                # Don't treat "No pages found" as an error that should stop indexing
                if "No pages found" in error:
                    logger.info(f"No BookStack pages found: {error}")
                    logger.info(
                        "No pages found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no pages found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No BookStack pages found in date range {start_date_str} to {end_date_str}",
                        {"pages_found": 0},
                    )
                    return 0, None
                else:
                    logger.error(f"Failed to get BookStack pages: {error}")
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get BookStack pages: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get BookStack pages: {error}"

            logger.info(f"Retrieved {len(pages)} pages from BookStack API")

        except Exception as e:
            logger.error(f"Error fetching BookStack pages: {e!s}", exc_info=True)
            return 0, f"Error fetching BookStack pages: {e!s}"

        # =======================================================================
        # PHASE 1: Analyze all pages, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        documents_indexed = 0
        skipped_pages = []
        documents_skipped = 0
        documents_failed = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        pages_to_process = []  # List of dicts with document and page data
        new_documents_created = False

        for page in pages:
            try:
                page_id = page.get("id")
                page_name = page.get("name", "")
                page_slug = page.get("slug", "")
                book_id = page.get("book_id")
                book_slug = page.get("book_slug", "")
                chapter_id = page.get("chapter_id")

                if not page_id or not page_name:
                    logger.warning(
                        f"Skipping page with missing ID or name: {page_id or 'Unknown'}"
                    )
                    skipped_pages.append(f"{page_name or 'Unknown'} (missing data)")
                    documents_skipped += 1
                    continue

                # Fetch full page content (Markdown preferred)
                try:
                    _, page_content = bookstack_client.get_page_with_content(
                        page_id, use_markdown=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch content for page {page_name}: {e}")
                    skipped_pages.append(f"{page_name} (content fetch error)")
                    documents_skipped += 1
                    continue

                # Build full content with title
                full_content = f"# {page_name}\n\n{page_content}"

                if not full_content.strip():
                    logger.warning(f"Skipping page with no content: {page_name}")
                    skipped_pages.append(f"{page_name} (no content)")
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this BookStack page
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.BOOKSTACK_CONNECTOR, page_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(full_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Build page URL
                page_url = f"{bookstack_base_url}/books/{book_slug}/page/{page_slug}"

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        # Ensure status is ready (might have been stuck in processing/pending)
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        logger.info(
                            f"Document for BookStack page {page_name} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    pages_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "page_id": page_id,
                            "page_name": page_name,
                            "page_slug": page_slug,
                            "book_id": book_id,
                            "book_slug": book_slug,
                            "chapter_id": chapter_id,
                            "page_url": page_url,
                            "page_content": page_content,
                            "full_content": full_content,
                            "content_hash": content_hash,
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
                        f"BookStack page {page_name} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=page_name,
                    document_type=DocumentType.BOOKSTACK_CONNECTOR,
                    document_metadata={
                        "page_id": page_id,
                        "page_name": page_name,
                        "page_slug": page_slug,
                        "book_id": book_id,
                        "book_slug": book_slug,
                        "chapter_id": chapter_id,
                        "base_url": bookstack_base_url,
                        "page_url": page_url,
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
                        "page_id": page_id,
                        "page_name": page_name,
                        "page_slug": page_slug,
                        "book_id": book_id,
                        "book_slug": book_slug,
                        "chapter_id": chapter_id,
                        "page_url": page_url,
                        "page_content": page_content,
                        "full_content": full_content,
                        "content_hash": content_hash,
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

                # Build document metadata
                doc_metadata = {
                    "page_id": item["page_id"],
                    "page_name": item["page_name"],
                    "page_slug": item["page_slug"],
                    "book_id": item["book_id"],
                    "book_slug": item["book_slug"],
                    "chapter_id": item["chapter_id"],
                    "base_url": bookstack_base_url,
                    "page_url": item["page_url"],
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "connector_id": connector_id,
                }

                if user_llm and connector.enable_summary:
                    summary_metadata = {
                        "page_name": item["page_name"],
                        "page_id": item["page_id"],
                        "book_id": item["book_id"],
                        "document_type": "BookStack Page",
                        "connector_type": "BookStack",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        item["full_content"], user_llm, summary_metadata
                    )
                else:
                    summary_content = f"BookStack Page: {item['page_name']}\n\nBook ID: {item['book_id']}\n\n{item['full_content']}"
                    summary_embedding = embed_text(summary_content)

                # Process chunks - using the full page content
                chunks = await create_document_chunks(item["full_content"])

                # Update document to READY with actual content
                document.title = item["page_name"]
                document.content = summary_content
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = doc_metadata
                safe_set_chunks(document, chunks)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                documents_indexed += 1

                # Batch commit every 10 documents (for ready status updates)
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} BookStack pages processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing page {item.get('page_name', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(e))
                    document.updated_at = get_current_timestamp()
                except Exception as status_error:
                    logger.error(
                        f"Failed to update document status to failed: {status_error}"
                    )
                skipped_pages.append(
                    f"{item.get('page_name', 'Unknown')} (processing error)"
                )
                documents_failed += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} BookStack pages processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all BookStack document changes to database"
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

        # Build warning message if there were issues
        warning_parts = []
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed BookStack indexing for connector {connector_id}",
            {
                "pages_processed": documents_indexed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "skipped_pages_count": len(skipped_pages),
            },
        )

        logger.info(
            f"BookStack indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed"
        )
        return documents_indexed, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during BookStack indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index BookStack pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index BookStack pages: {e!s}", exc_info=True)
        return 0, f"Failed to index BookStack pages: {e!s}"
