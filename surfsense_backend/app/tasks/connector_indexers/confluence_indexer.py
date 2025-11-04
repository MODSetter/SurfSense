"""
Confluence connector indexer.
"""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.confluence_connector import ConfluenceConnector
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
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_confluence_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Confluence pages and comments.

    Args:
        session: Database session
        connector_id: ID of the Confluence connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="confluence_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Confluence pages indexing for connector {connector_id}",
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
            session, connector_id, SearchSourceConnectorType.CONFLUENCE_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the Confluence credentials from the connector config
        confluence_email = connector.config.get("CONFLUENCE_EMAIL")
        confluence_api_token = connector.config.get("CONFLUENCE_API_TOKEN")
        confluence_base_url = connector.config.get("CONFLUENCE_BASE_URL")

        if not confluence_email or not confluence_api_token or not confluence_base_url:
            await task_logger.log_task_failure(
                log_entry,
                f"Confluence credentials not found in connector config for connector {connector_id}",
                "Missing Confluence credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Confluence credentials not found in connector config"

        # Initialize Confluence client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Confluence client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        confluence_client = ConfluenceConnector(
            base_url=confluence_base_url,
            email=confluence_email,
            api_token=confluence_api_token,
        )

        # Calculate date range
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Confluence pages from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_pages",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get pages within date range
        try:
            pages, error = confluence_client.get_pages_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Confluence pages: {error}")

                # Don't treat "No pages found" as an error that should stop indexing
                if "No pages found" in error:
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
                        f"No Confluence pages found in date range {start_date_str} to {end_date_str}",
                        {"pages_found": 0},
                    )
                    return 0, None
                else:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Confluence pages: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Confluence pages: {error}"

            logger.info(f"Retrieved {len(pages)} pages from Confluence API")

        except Exception as e:
            logger.error(f"Error fetching Confluence pages: {e!s}", exc_info=True)
            return 0, f"Error fetching Confluence pages: {e!s}"

        # Process and index each page
        documents_indexed = 0
        skipped_pages = []
        documents_skipped = 0

        for page in pages:
            try:
                page_id = page.get("id")
                page_title = page.get("title", "")
                space_id = page.get("spaceId", "")

                if not page_id or not page_title:
                    logger.warning(
                        f"Skipping page with missing ID or title: {page_id or 'Unknown'}"
                    )
                    skipped_pages.append(f"{page_title or 'Unknown'} (missing data)")
                    documents_skipped += 1
                    continue

                # Extract page content
                page_content = ""
                if page.get("body") and page["body"].get("storage"):
                    page_content = page["body"]["storage"].get("value", "")

                # Add comments to content
                comments = page.get("comments", [])
                comments_content = ""
                if comments:
                    comments_content = "\n\n## Comments\n\n"
                    for comment in comments:
                        comment_body = ""
                        if comment.get("body") and comment["body"].get("storage"):
                            comment_body = comment["body"]["storage"].get("value", "")

                        comment_author = comment.get("version", {}).get(
                            "authorId", "Unknown"
                        )
                        comment_date = comment.get("version", {}).get("createdAt", "")

                        comments_content += f"**Comment by {comment_author}** ({comment_date}):\n{comment_body}\n\n"

                # Combine page content with comments
                full_content = f"# {page_title}\n\n{page_content}{comments_content}"

                if not full_content.strip():
                    logger.warning(f"Skipping page with no content: {page_title}")
                    skipped_pages.append(f"{page_title} (no content)")
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this Confluence page
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.CONFLUENCE_CONNECTOR, page_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(full_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                comment_count = len(comments)

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for Confluence page {page_title} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Confluence page {page_title}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "page_title": page_title,
                                "page_id": page_id,
                                "space_id": space_id,
                                "comment_count": comment_count,
                                "document_type": "Confluence Page",
                                "connector_type": "Confluence",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                full_content, user_llm, document_metadata
                            )
                        else:
                            summary_content = f"Confluence Page: {page_title}\n\nSpace ID: {space_id}\n\n"
                            if page_content:
                                content_preview = page_content[:1000]
                                if len(page_content) > 1000:
                                    content_preview += "..."
                                summary_content += (
                                    f"Content Preview: {content_preview}\n\n"
                                )
                            summary_content += f"Comments: {comment_count}"
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(full_content)

                        # Update existing document
                        existing_document.title = f"Confluence - {page_title}"
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "page_id": page_id,
                            "page_title": page_title,
                            "space_id": space_id,
                            "comment_count": comment_count,
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        existing_document.chunks = chunks

                        documents_indexed += 1
                        logger.info(
                            f"Successfully updated Confluence page {page_title}"
                        )
                        continue

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "page_title": page_title,
                        "page_id": page_id,
                        "space_id": space_id,
                        "comment_count": comment_count,
                        "document_type": "Confluence Page",
                        "connector_type": "Confluence",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        full_content, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = (
                        f"Confluence Page: {page_title}\n\nSpace ID: {space_id}\n\n"
                    )
                    if page_content:
                        # Take first 500 characters of content for summary
                        content_preview = page_content[:1000]
                        if len(page_content) > 1000:
                            content_preview += "..."
                        summary_content += f"Content Preview: {content_preview}\n\n"
                    summary_content += f"Comments: {comment_count}"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                # Process chunks - using the full page content with comments
                chunks = await create_document_chunks(full_content)

                # Create and store new document
                logger.info(f"Creating new document for page {page_title}")
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Confluence - {page_title}",
                    document_type=DocumentType.CONFLUENCE_CONNECTOR,
                    document_metadata={
                        "page_id": page_id,
                        "page_title": page_title,
                        "space_id": space_id,
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new page {page_title}")

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Confluence pages processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing page {page.get('title', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_pages.append(
                    f"{page.get('title', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this page and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} Confluence pages processed"
        )
        await session.commit()
        logger.info(
            "Successfully committed all Confluence document changes to database"
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Confluence indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_pages_count": len(skipped_pages),
            },
        )

        logger.info(
            f"Confluence indexing completed: {documents_indexed} new pages, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Confluence indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Confluence pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Confluence pages: {e!s}", exc_info=True)
        return 0, f"Failed to index Confluence pages: {e!s}"
