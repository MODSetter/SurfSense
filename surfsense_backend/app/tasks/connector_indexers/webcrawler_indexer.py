"""
Webcrawler connector indexer.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.webcrawler_connector import WebCrawlerConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
from app.utils.webcrawler_utils import parse_webcrawler_urls

from .base import (
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


async def index_crawled_urls(
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
    Index web page URLs.

    Args:
        session: Database session
        connector_id: ID of the webcrawler connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for filtering (YYYY-MM-DD format) - optional
        end_date: End date for filtering (YYYY-MM-DD format) - optional
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="crawled_url_indexing",
        source="connector_indexing_task",
        message=f"Starting web page URL indexing for connector {connector_id}",
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
            f"Retrieving webcrawler connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.WEBCRAWLER_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a webcrawler connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a webcrawler connector",
            )

        # Get the Firecrawl API key from the connector config (optional)
        api_key = connector.config.get("FIRECRAWL_API_KEY")

        # Get URLs from connector config
        urls = parse_webcrawler_urls(connector.config.get("INITIAL_URLS"))

        logger.info(
            f"Starting crawled web page indexing for connector {connector_id} with {len(urls)} URLs"
        )

        # Initialize webcrawler client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing webcrawler client for connector {connector_id}",
            {
                "stage": "client_initialization",
                "use_firecrawl": bool(api_key),
            },
        )

        crawler = WebCrawlerConnector(firecrawl_api_key=api_key)

        # Validate URLs
        if not urls:
            await task_logger.log_task_failure(
                log_entry,
                "No URLs provided for indexing",
                "Empty URL list",
                {"error_type": "ValidationError"},
            )
            return 0, "No URLs provided for indexing"

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to crawl {len(urls)} URLs",
            {
                "stage": "crawling",
                "total_urls": len(urls),
            },
        )

        documents_indexed = 0
        documents_updated = 0
        documents_skipped = 0
        failed_urls = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        for idx, url in enumerate(urls, 1):
            # Check if it's time for a heartbeat update
            if (
                on_heartbeat_callback
                and (time.time() - last_heartbeat_time) >= HEARTBEAT_INTERVAL_SECONDS
            ):
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = time.time()
            try:
                logger.info(f"Processing URL {idx}/{len(urls)}: {url}")

                await task_logger.log_task_progress(
                    log_entry,
                    f"Crawling URL {idx}/{len(urls)}: {url}",
                    {
                        "stage": "crawling_url",
                        "url_index": idx,
                        "url": url,
                    },
                )

                # Crawl the URL
                crawl_result, error = await crawler.crawl_url(url)

                if error or not crawl_result:
                    logger.warning(f"Failed to crawl URL {url}: {error}")
                    failed_urls.append((url, error or "Unknown error"))
                    continue

                # Extract content and metadata
                content = crawl_result.get("content", "")
                metadata = crawl_result.get("metadata", {})
                crawler_type = crawl_result.get("crawler_type", "unknown")

                if not content.strip():
                    logger.warning(f"Skipping URL with no content: {url}")
                    failed_urls.append((url, "No content extracted"))
                    documents_skipped += 1
                    continue

                # Format content as structured document for summary generation (includes all metadata)
                structured_document = crawler.format_to_structured_document(
                    crawl_result
                )

                # Generate unique identifier hash for this URL
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.CRAWLED_URL, url, search_space_id
                )

                # Generate content hash using a version WITHOUT metadata
                # This ensures the hash only changes when actual content changes,
                # not when metadata (which contains dynamic fields like timestamps, IDs, etc.) changes
                structured_document_for_hash = crawler.format_to_structured_document(
                    crawl_result, exclude_metadata=True
                )
                content_hash = generate_content_hash(
                    structured_document_for_hash, search_space_id
                )

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Extract useful metadata
                title = metadata.get("title", url)
                description = metadata.get("description", "")
                language = metadata.get("language", "")

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(f"Document for URL {url} unchanged. Skipping.")
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for URL {url}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "url": url,
                                "title": title,
                                "description": description,
                                "language": language,
                                "document_type": "Crawled URL",
                                "crawler_type": crawler_type,
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                structured_document, user_llm, document_metadata
                            )
                        else:
                            # Fallback to simple summary if no LLM configured
                            summary_content = f"Crawled URL: {title}\n\n"
                            summary_content += f"URL: {url}\n"
                            if description:
                                summary_content += f"Description: {description}\n"
                            if language:
                                summary_content += f"Language: {language}\n"
                            summary_content += f"Crawler: {crawler_type}\n\n"

                            # Add content preview
                            content_preview = content[:1000]
                            if len(content) > 1000:
                                content_preview += "..."
                            summary_content += f"Content Preview:\n{content_preview}\n"

                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(content)

                        # Update existing document
                        existing_document.title = title
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            **metadata,
                            "crawler_type": crawler_type,
                            "last_crawled_at": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                        existing_document.chunks = chunks
                        existing_document.updated_at = get_current_timestamp()

                        documents_updated += 1
                        logger.info(f"Successfully updated URL {url}")
                        continue

                # Document doesn't exist by unique_identifier_hash
                # Check if a document with the same content_hash exists (from another connector)
                with session.no_autoflush:
                    duplicate_by_content = await check_duplicate_document_by_hash(
                        session, content_hash
                    )

                if duplicate_by_content:
                    logger.info(
                        f"URL {url} already indexed by another connector "
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
                    document_metadata = {
                        "url": url,
                        "title": title,
                        "description": description,
                        "language": language,
                        "document_type": "Crawled URL",
                        "crawler_type": crawler_type,
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        structured_document, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = f"Crawled URL: {title}\n\n"
                    summary_content += f"URL: {url}\n"
                    if description:
                        summary_content += f"Description: {description}\n"
                    if language:
                        summary_content += f"Language: {language}\n"
                    summary_content += f"Crawler: {crawler_type}\n\n"

                    # Add content preview
                    content_preview = content[:1000]
                    if len(content) > 1000:
                        content_preview += "..."
                    summary_content += f"Content Preview:\n{content_preview}\n"

                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                chunks = await create_document_chunks(content)

                document = Document(
                    search_space_id=search_space_id,
                    title=title,
                    document_type=DocumentType.CRAWLED_URL,
                    document_metadata={
                        **metadata,
                        "crawler_type": crawler_type,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
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
                logger.info(f"Successfully indexed new URL {url}")

                # Batch commit every 10 documents
                if (documents_indexed + documents_updated) % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed + documents_updated} URLs processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing URL {url}: {e!s}",
                    exc_info=True,
                )
                failed_urls.append((url, str(e)))
                continue

        total_processed = documents_indexed + documents_updated

        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} new, {documents_updated} updated URLs processed"
        )
        await session.commit()

        # Log failed URLs if any (for debugging purposes)
        if failed_urls:
            failed_summary = "; ".join(
                [f"{url}: {error}" for url, error in failed_urls[:5]]
            )
            if len(failed_urls) > 5:
                failed_summary += f" (and {len(failed_urls) - 5} more)"
            logger.warning(f"Some URLs failed to index: {failed_summary}")

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed crawled web page indexing for connector {connector_id}",
            {
                "urls_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_updated": documents_updated,
                "documents_skipped": documents_skipped,
                "failed_urls_count": len(failed_urls),
            },
        )

        logger.info(
            f"Web page indexing completed: {documents_indexed} new, "
            f"{documents_updated} updated, {documents_skipped} skipped, "
            f"{len(failed_urls)} failed"
        )
        return (
            total_processed,
            None,
        )  # Return None on success (result_message is for logging only)

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during web page indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index web page URLs for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index web page URLs: {e!s}", exc_info=True)
        return 0, f"Failed to index web page URLs: {e!s}"


async def get_crawled_url_documents(
    session: AsyncSession,
    search_space_id: int,
    connector_id: int | None = None,
) -> list[Document]:
    """
    Get all crawled URL documents for a search space.

    Args:
        session: Database session
        search_space_id: ID of the search space
        connector_id: Optional connector ID to filter by

    Returns:
        List of Document objects
    """
    from sqlalchemy import select

    query = select(Document).filter(
        Document.search_space_id == search_space_id,
        Document.document_type == DocumentType.CRAWLED_URL,
    )

    if connector_id:
        # Filter by connector if needed - you might need to add a connector_id field to Document
        # or filter by some other means depending on your schema
        pass

    result = await session.execute(query)
    documents = result.scalars().all()
    return list(documents)
