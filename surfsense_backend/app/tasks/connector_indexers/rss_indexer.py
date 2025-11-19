"""
RSS Feed connector indexer.
"""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.rss_connector import RSSConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_rss_feeds(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index RSS feed entries with deduplication.

    Args:
        session: Database session
        connector_id: ID of the RSS connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for filtering entries (ISO format)
        end_date: End date for filtering entries (ISO format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="rss_feed_indexing",
        source="connector_indexing_task",
        message=f"Starting RSS feed indexing for connector {connector_id}",
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
            session, connector_id, SearchSourceConnectorType.RSS_FEED_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get feed URLs from the connector config
        feed_urls = connector.config.get("FEED_URLS", [])

        if not feed_urls:
            await task_logger.log_task_failure(
                log_entry,
                f"No feed URLs configured for connector {connector_id}",
                "No feed URLs",
                {"error_type": "MissingConfiguration"},
            )
            return 0, "No feed URLs configured"

        # Initialize RSS client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing RSS connector for {len(feed_urls)} feeds",
            {"stage": "client_initialization", "feed_count": len(feed_urls)},
        )

        rss_client = RSSConnector(feed_urls=feed_urls)

        # Parse date filters
        filter_start = None
        filter_end = None
        if start_date:
            try:
                filter_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}")
        if end_date:
            try:
                filter_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}")

        await task_logger.log_task_progress(
            log_entry,
            "Fetching RSS feed entries",
            {"stage": "fetching_data"},
        )

        # Fetch all entries
        entries = await rss_client.fetch_all_feeds()

        if not entries:
            logger.info("No entries found to index from RSS feeds")
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()

            await task_logger.log_task_success(
                log_entry,
                "No entries found to index",
                {"items_indexed": 0},
            )
            return 0, None

        await task_logger.log_task_progress(
            log_entry,
            f"Processing {len(entries)} entries from RSS feeds",
            {"stage": "processing_items", "total_items": len(entries)},
        )

        # Process each entry
        documents_indexed = 0
        duplicates_skipped = 0

        for entry in entries:
            try:
                # Apply date filters
                if entry.get("published"):
                    try:
                        entry_date = datetime.fromisoformat(
                            entry["published"].replace("Z", "+00:00")
                        )
                        if filter_start and entry_date < filter_start:
                            continue
                        if filter_end and entry_date > filter_end:
                            continue
                    except (ValueError, TypeError):
                        pass  # Skip date filtering if parse fails

                # Use the unique_id from the connector for deduplication
                unique_id = entry.get("unique_id", "")
                if not unique_id:
                    # Fallback: generate from link and title
                    unique_id = f"{entry.get('link', '')}_{entry.get('title', '')}"

                unique_identifier_hash = generate_unique_identifier_hash(unique_id)

                # Check for existing document (deduplication)
                existing_doc = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Format content to markdown
                content = RSSConnector.format_entry_to_markdown(entry)
                content_hash = generate_content_hash(content)

                # Build metadata
                metadata = {
                    "feed_url": entry.get("feed_url", ""),
                    "feed_title": entry.get("feed_title", ""),
                    "link": entry.get("link", ""),
                    "author": entry.get("author", ""),
                    "published": entry.get("published", ""),
                    "guid": entry.get("guid", ""),
                    "categories": entry.get("categories", []),
                }

                # Generate title
                title = f"RSS: {entry.get('title', 'Untitled')}"

                if existing_doc:
                    # Check if content has changed
                    if existing_doc.content_hash == content_hash:
                        logger.debug(f"Skipping unchanged entry: {entry.get('title', 'Untitled')}")
                        duplicates_skipped += 1
                        continue

                    # Update existing document
                    existing_doc.title = title
                    existing_doc.content = content
                    existing_doc.content_hash = content_hash
                    existing_doc.document_metadata = metadata

                    # Delete old chunks and create new ones
                    existing_doc.chunks.clear()

                    # Create new chunks
                    chunks = create_document_chunks(
                        content,
                        existing_doc,
                        config.chunker_instance,
                        config.embedding_model_instance,
                    )
                    for chunk in chunks:
                        existing_doc.chunks.append(chunk)

                    documents_indexed += 1
                    logger.info(f"Updated existing RSS entry: {entry.get('title', 'Untitled')}")

                else:
                    # Create new document
                    document = Document(
                        title=title,
                        document_type=DocumentType.RSS_FEED_CONNECTOR,
                        document_metadata=metadata,
                        content=content,
                        content_hash=content_hash,
                        unique_identifier_hash=unique_identifier_hash,
                        search_space_id=search_space_id,
                    )

                    # Create chunks
                    chunks = create_document_chunks(
                        content,
                        document,
                        config.chunker_instance,
                        config.embedding_model_instance,
                    )
                    for chunk in chunks:
                        document.chunks.append(chunk)

                    session.add(document)
                    documents_indexed += 1
                    logger.info(f"Indexed new RSS entry: {entry.get('title', 'Untitled')}")

            except Exception as e:
                logger.error(f"Error processing entry {entry.get('title', 'unknown')}: {e!s}")
                continue

        # Update last indexed timestamp
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Commit all changes
        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully indexed {documents_indexed} RSS entries, skipped {duplicates_skipped} duplicates",
            {
                "items_indexed": documents_indexed,
                "duplicates_skipped": duplicates_skipped,
                "total_entries": len(entries),
            },
        )

        logger.info(
            f"Successfully indexed {documents_indexed} RSS entries, skipped {duplicates_skipped} duplicates"
        )
        return documents_indexed, None

    except SQLAlchemyError as e:
        await session.rollback()
        error_message = f"Database error during RSS indexing: {e!s}"
        logger.error(error_message)

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            "Database error",
            {"error_type": "DatabaseError"},
        )
        return 0, error_message

    except Exception as e:
        await session.rollback()
        error_message = f"Unexpected error during RSS indexing: {e!s}"
        logger.error(error_message)

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            "Unexpected error",
            {"error_type": "UnexpectedError"},
        )
        return 0, error_message
