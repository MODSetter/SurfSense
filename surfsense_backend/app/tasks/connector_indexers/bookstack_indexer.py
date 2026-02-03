"""
BookStack connector indexer.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.bookstack_connector import BookStackConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
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

        # Process and index each page
        documents_indexed = 0
        skipped_pages = []
        documents_skipped = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        for page in pages:
            # Check if it's time for a heartbeat update
            if (
                on_heartbeat_callback
                and (time.time() - last_heartbeat_time) >= HEARTBEAT_INTERVAL_SECONDS
            ):
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = time.time()
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
                    page_detail, page_content = bookstack_client.get_page_with_content(
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

                # Build document metadata
                doc_metadata = {
                    "page_id": page_id,
                    "page_name": page_name,
                    "page_slug": page_slug,
                    "book_id": book_id,
                    "book_slug": book_slug,
                    "chapter_id": chapter_id,
                    "base_url": bookstack_base_url,
                    "page_url": page_url,
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for BookStack page {page_name} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for BookStack page {page_name}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            summary_metadata = {
                                "page_name": page_name,
                                "page_id": page_id,
                                "book_id": book_id,
                                "document_type": "BookStack Page",
                                "connector_type": "BookStack",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                full_content, user_llm, summary_metadata
                            )
                        else:
                            summary_content = (
                                f"BookStack Page: {page_name}\n\nBook ID: {book_id}\n\n"
                            )
                            if page_content:
                                content_preview = page_content[:1000]
                                if len(page_content) > 1000:
                                    content_preview += "..."
                                summary_content += (
                                    f"Content Preview: {content_preview}\n\n"
                                )
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(full_content)

                        # Update existing document
                        existing_document.title = f"BookStack - {page_name}"
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = doc_metadata
                        existing_document.chunks = chunks
                        existing_document.updated_at = get_current_timestamp()

                        documents_indexed += 1
                        logger.info(f"Successfully updated BookStack page {page_name}")
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

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    summary_metadata = {
                        "page_name": page_name,
                        "page_id": page_id,
                        "book_id": book_id,
                        "document_type": "BookStack Page",
                        "connector_type": "BookStack",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        full_content, user_llm, summary_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = (
                        f"BookStack Page: {page_name}\n\nBook ID: {book_id}\n\n"
                    )
                    if page_content:
                        # Take first 1000 characters of content for summary
                        content_preview = page_content[:1000]
                        if len(page_content) > 1000:
                            content_preview += "..."
                        summary_content += f"Content Preview: {content_preview}\n\n"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                # Process chunks - using the full page content
                chunks = await create_document_chunks(full_content)

                # Create and store new document
                logger.info(f"Creating new document for page {page_name}")
                document = Document(
                    search_space_id=search_space_id,
                    title=f"BookStack - {page_name}",
                    document_type=DocumentType.BOOKSTACK_CONNECTOR,
                    document_metadata=doc_metadata,
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                    updated_at=get_current_timestamp(),
                    created_by_id=user_id,
                    connector_id=connector_id,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new page {page_name}")

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} BookStack pages processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing page {page.get('name', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_pages.append(
                    f"{page.get('name', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this page and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} BookStack pages processed"
        )
        await session.commit()
        logger.info("Successfully committed all BookStack document changes to database")

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed BookStack indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_pages_count": len(skipped_pages),
            },
        )

        logger.info(
            f"BookStack indexing completed: {documents_indexed} new pages, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

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
