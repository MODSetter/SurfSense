"""
Composio connector indexer.

Routes indexing requests to toolkit-specific handlers (Google Drive, Gmail, Calendar).

Note: This module is intentionally placed in app/tasks/ (not in connector_indexers/)
to avoid circular import issues with the connector_indexers package.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import config
from app.connectors.composio_connector import ComposioConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.services.composio_service import INDEXABLE_TOOLKITS, TOOLKIT_TO_DOCUMENT_TYPE
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import calculate_date_range
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

# Set up logging
logger = logging.getLogger(__name__)


# ============ Utility functions (copied from connector_indexers.base to avoid circular imports) ============


def get_current_timestamp() -> datetime:
    """Get the current timestamp with timezone for updated_at field."""
    return datetime.now(UTC)


async def check_document_by_unique_identifier(
    session: AsyncSession, unique_identifier_hash: str
) -> Document | None:
    """Check if a document with the given unique identifier hash already exists."""
    existing_doc_result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.unique_identifier_hash == unique_identifier_hash)
    )
    return existing_doc_result.scalars().first()


async def get_connector_by_id(
    session: AsyncSession, connector_id: int, connector_type: SearchSourceConnectorType | None
) -> SearchSourceConnector | None:
    """Get a connector by ID and optionally by type from the database."""
    query = select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    if connector_type is not None:
        query = query.filter(SearchSourceConnector.connector_type == connector_type)
    result = await session.execute(query)
    return result.scalars().first()


async def update_connector_last_indexed(
    session: AsyncSession,
    connector: SearchSourceConnector,
    update_last_indexed: bool = True,
) -> None:
    """Update the last_indexed_at timestamp for a connector."""
    if update_last_indexed:
        connector.last_indexed_at = datetime.now(UTC)  # Use UTC for timezone consistency
        logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")


# ============ Main indexer function ============


async def index_composio_connector(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    max_items: int = 1000,
) -> tuple[int, str]:
    """
    Index content from a Composio connector.

    Routes to toolkit-specific indexing based on the connector's toolkit_id.

    Args:
        session: Database session
        connector_id: ID of the Composio connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for filtering (YYYY-MM-DD format)
        end_date: End date for filtering (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp
        max_items: Maximum number of items to fetch

    Returns:
        Tuple of (number_of_indexed_items, error_message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="composio_connector_indexing",
        source="connector_indexing_task",
        message=f"Starting Composio connector indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "max_items": max_items,
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get connector by id - accept any Composio connector type
        # We'll check the actual type after loading
        connector = await get_connector_by_id(
            session, connector_id, None  # Don't filter by type, we'll validate after
        )
        
        # Validate it's a Composio connector
        if connector and connector.connector_type not in [
            SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        ]:
            error_msg = f"Connector {connector_id} is not a Composio connector"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "InvalidConnectorType"}
            )
            return 0, error_msg

        if not connector:
            error_msg = f"Composio connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        # Get toolkit ID from config
        toolkit_id = connector.config.get("toolkit_id")
        if not toolkit_id:
            error_msg = f"Composio connector {connector_id} has no toolkit_id configured"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "MissingToolkitId"}
            )
            return 0, error_msg

        # Check if toolkit is indexable
        if toolkit_id not in INDEXABLE_TOOLKITS:
            error_msg = f"Toolkit '{toolkit_id}' does not support indexing yet"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ToolkitNotIndexable"}
            )
            return 0, error_msg

        # Route to toolkit-specific indexer
        if toolkit_id == "googledrive":
            return await _index_composio_google_drive(
                session=session,
                connector=connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                task_logger=task_logger,
                log_entry=log_entry,
                update_last_indexed=update_last_indexed,
                max_items=max_items,
            )
        elif toolkit_id == "gmail":
            return await _index_composio_gmail(
                session=session,
                connector=connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                task_logger=task_logger,
                log_entry=log_entry,
                update_last_indexed=update_last_indexed,
                max_items=max_items,
            )
        elif toolkit_id == "googlecalendar":
            return await _index_composio_google_calendar(
                session=session,
                connector=connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                task_logger=task_logger,
                log_entry=log_entry,
                update_last_indexed=update_last_indexed,
                max_items=max_items,
            )
        else:
            error_msg = f"No indexer implemented for toolkit: {toolkit_id}"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "NoIndexerImplemented"}
            )
            return 0, error_msg

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Composio indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Composio connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Composio connector: {e!s}", exc_info=True)
        return 0, f"Failed to index Composio connector: {e!s}"


async def _index_composio_google_drive(
    session: AsyncSession,
    connector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry,
    update_last_indexed: bool = True,
    max_items: int = 1000,
) -> tuple[int, str]:
    """Index Google Drive files via Composio."""
    try:
        composio_connector = ComposioConnector(session, connector_id)

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Google Drive files via Composio for connector {connector_id}",
            {"stage": "fetching_files"},
        )

        # Fetch files
        all_files = []
        page_token = None

        while len(all_files) < max_items:
            files, next_token, error = await composio_connector.list_drive_files(
                page_token=page_token,
                page_size=min(100, max_items - len(all_files)),
            )

            if error:
                await task_logger.log_task_failure(
                    log_entry, f"Failed to fetch Drive files: {error}", {}
                )
                return 0, f"Failed to fetch Drive files: {error}"

            all_files.extend(files)

            if not next_token:
                break
            page_token = next_token

        if not all_files:
            success_msg = "No Google Drive files found"
            await task_logger.log_task_success(
                log_entry, success_msg, {"files_count": 0}
            )
            # CRITICAL: Update timestamp even when no files found so Electric SQL syncs and UI shows indexed status
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return 0, None  # Return None (not error) when no items found - this is success with 0 items

        logger.info(f"Found {len(all_files)} Google Drive files to index via Composio")

        documents_indexed = 0
        documents_skipped = 0

        for file_info in all_files:
            try:
                # Handle both standard Google API and potential Composio variations
                file_id = file_info.get("id", "") or file_info.get("fileId", "")
                file_name = file_info.get("name", "") or file_info.get("fileName", "") or "Untitled"
                mime_type = file_info.get("mimeType", "") or file_info.get("mime_type", "")

                if not file_id:
                    documents_skipped += 1
                    continue

                # Skip folders
                if mime_type == "application/vnd.google-apps.folder":
                    continue

                # Generate unique identifier hash
                document_type = DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googledrive"])
                unique_identifier_hash = generate_unique_identifier_hash(
                    document_type, f"drive_{file_id}", search_space_id
                )

                # Check if document exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Get file content
                content, content_error = await composio_connector.get_drive_file_content(
                    file_id
                )

                if content_error or not content:
                    logger.warning(f"Could not get content for file {file_name}: {content_error}")
                    # Use metadata as content fallback
                    markdown_content = f"# {file_name}\n\n"
                    markdown_content += f"**File ID:** {file_id}\n"
                    markdown_content += f"**Type:** {mime_type}\n"
                else:
                    try:
                        markdown_content = content.decode("utf-8")
                    except UnicodeDecodeError:
                        markdown_content = f"# {file_name}\n\n[Binary file content]\n"

                content_hash = generate_content_hash(markdown_content, search_space_id)

                if existing_document:
                    if existing_document.content_hash == content_hash:
                        documents_skipped += 1
                        continue

                    # Update existing document
                    user_llm = await get_user_long_context_llm(
                        session, user_id, search_space_id
                    )

                    if user_llm:
                        document_metadata = {
                            "file_id": file_id,
                            "file_name": file_name,
                            "mime_type": mime_type,
                            "document_type": "Google Drive File (Composio)",
                        }
                        summary_content, summary_embedding = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )
                    else:
                        summary_content = f"Google Drive File: {file_name}\n\nType: {mime_type}"
                        summary_embedding = config.embedding_model_instance.embed(summary_content)

                    chunks = await create_document_chunks(markdown_content)

                    existing_document.title = f"Drive: {file_name}"
                    existing_document.content = summary_content
                    existing_document.content_hash = content_hash
                    existing_document.embedding = summary_embedding
                    existing_document.document_metadata = {
                        "file_id": file_id,
                        "file_name": file_name,
                        "mime_type": mime_type,
                        "connector_id": connector_id,
                        "source": "composio",
                    }
                    existing_document.chunks = chunks
                    existing_document.updated_at = get_current_timestamp()

                    documents_indexed += 1
                    
                    # Batch commit every 10 documents 
                    if documents_indexed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_indexed} Google Drive files processed so far"
                        )
                        await session.commit()
                    continue

                # Create new document
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "file_id": file_id,
                        "file_name": file_name,
                        "mime_type": mime_type,
                        "document_type": "Google Drive File (Composio)",
                    }
                    summary_content, summary_embedding = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = f"Google Drive File: {file_name}\n\nType: {mime_type}"
                    summary_embedding = config.embedding_model_instance.embed(summary_content)

                chunks = await create_document_chunks(markdown_content)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Drive: {file_name}",
                    document_type=DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googledrive"]),
                    document_metadata={
                        "file_id": file_id,
                        "file_name": file_name,
                        "mime_type": mime_type,
                        "connector_id": connector_id,
                        "toolkit_id": "googledrive",
                        "source": "composio",
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                    updated_at=get_current_timestamp(),
                )
                session.add(document)
                documents_indexed += 1

                # Batch commit every 10 documents 
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Google Drive files processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Drive file: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted (safety net)
        # This matches the pattern used in non-Composio Gmail indexer
        logger.info(
            f"Final commit: Total {documents_indexed} Google Drive files processed"
        )
        await session.commit()
        logger.info(
            "Successfully committed all Composio Google Drive document changes to database"
        )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Drive indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
            },
        )

        return documents_indexed, None

    except Exception as e:
        logger.error(f"Failed to index Google Drive via Composio: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Drive via Composio: {e!s}"


async def _process_gmail_message_batch(
    session: AsyncSession,
    messages: list[dict[str, Any]],
    composio_connector: ComposioConnector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    total_documents_indexed: int = 0,
) -> tuple[int, int]:
    """
    Process a batch of Gmail messages and index them.
    
    Args:
        total_documents_indexed: Running total of documents indexed so far (for batch commits).
    
    Returns:
        Tuple of (documents_indexed, documents_skipped)
    """
    documents_indexed = 0
    documents_skipped = 0

    for message in messages:
        try:
            # Composio uses 'messageId' (camelCase), not 'id'
            message_id = message.get("messageId", "") or message.get("id", "")
            if not message_id:
                documents_skipped += 1
                continue

            # Composio's GMAIL_FETCH_EMAILS already returns full message content
            # No need for a separate detail API call

            # Extract message info from Composio response
            # Composio structure: messageId, messageText, messageTimestamp, payload.headers, labelIds
            payload = message.get("payload", {})
            headers = payload.get("headers", [])

            subject = "No Subject"
            sender = "Unknown Sender"
            date_str = message.get("messageTimestamp", "Unknown Date")

            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                if name == "subject":
                    subject = value
                elif name == "from":
                    sender = value
                elif name == "date":
                    date_str = value

            # Format to markdown using the full message data
            markdown_content = composio_connector.format_gmail_message_to_markdown(message)

            # Check for empty content (defensive parsing per Composio best practices)
            if not markdown_content.strip():
                logger.warning(f"Skipping Gmail message with no content: {subject}")
                documents_skipped += 1
                continue

            # Generate unique identifier
            document_type = DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["gmail"])
            unique_identifier_hash = generate_unique_identifier_hash(
                document_type, f"gmail_{message_id}", search_space_id
            )

            content_hash = generate_content_hash(markdown_content, search_space_id)

            existing_document = await check_document_by_unique_identifier(
                session, unique_identifier_hash
            )

            # Get label IDs from Composio response
            label_ids = message.get("labelIds", [])
            # Extract thread_id if available (for consistency with non-Composio implementation)
            thread_id = message.get("threadId", "") or message.get("thread_id", "")

            if existing_document:
                if existing_document.content_hash == content_hash:
                    documents_skipped += 1
                    continue

                # Update existing
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "subject": subject,
                        "sender": sender,
                        "document_type": "Gmail Message (Composio)",
                    }
                    summary_content, summary_embedding = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = f"Gmail: {subject}\n\nFrom: {sender}\nDate: {date_str}"
                    summary_embedding = config.embedding_model_instance.embed(summary_content)

                chunks = await create_document_chunks(markdown_content)

                existing_document.title = f"Gmail: {subject}"
                existing_document.content = summary_content
                existing_document.content_hash = content_hash
                existing_document.embedding = summary_embedding
                existing_document.document_metadata = {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "labels": label_ids,
                    "connector_id": connector_id,
                    "source": "composio",
                }
                existing_document.chunks = chunks
                existing_document.updated_at = get_current_timestamp()

                documents_indexed += 1
                
                # Batch commit every 10 documents 
                current_total = total_documents_indexed + documents_indexed
                if current_total % 10 == 0:
                    logger.info(
                        f"Committing batch: {current_total} Gmail messages processed so far"
                    )
                    await session.commit()
                continue

            # Create new document
            user_llm = await get_user_long_context_llm(
                session, user_id, search_space_id
            )

            if user_llm:
                document_metadata = {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "subject": subject,
                    "sender": sender,
                    "document_type": "Gmail Message (Composio)",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    markdown_content, user_llm, document_metadata
                )
            else:
                summary_content = f"Gmail: {subject}\n\nFrom: {sender}\nDate: {date_str}"
                summary_embedding = config.embedding_model_instance.embed(summary_content)

            chunks = await create_document_chunks(markdown_content)

            document = Document(
                search_space_id=search_space_id,
                title=f"Gmail: {subject}",
                document_type=DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["gmail"]),
                document_metadata={
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "labels": label_ids,
                    "connector_id": connector_id,
                    "toolkit_id": "gmail",
                    "source": "composio",
                },
                content=summary_content,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
                embedding=summary_embedding,
                chunks=chunks,
                updated_at=get_current_timestamp(),
            )
            session.add(document)
            documents_indexed += 1

            # Batch commit every 10 documents 
            current_total = total_documents_indexed + documents_indexed
            if current_total % 10 == 0:
                logger.info(
                    f"Committing batch: {current_total} Gmail messages processed so far"
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Error processing Gmail message: {e!s}", exc_info=True)
            documents_skipped += 1
            # Rollback on error to avoid partial state (per Composio best practices)
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error!s}", exc_info=True)
            continue

    return documents_indexed, documents_skipped


async def _index_composio_gmail(
    session: AsyncSession,
    connector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None,
    end_date: str | None,
    task_logger: TaskLoggingService,
    log_entry,
    update_last_indexed: bool = True,
    max_items: int = 1000,
) -> tuple[int, str]:
    """Index Gmail messages via Composio with pagination and incremental processing."""
    try:
        composio_connector = ComposioConnector(session, connector_id)

        # Normalize date values - handle "undefined" strings from frontend
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range with defaults (uses last_indexed_at or 365 days back)
        # This ensures indexing works even when user doesn't specify dates
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        # Build query with date range
        query_parts = []
        if start_date_str:
            query_parts.append(f"after:{start_date_str.replace('-', '/')}")
        if end_date_str:
            query_parts.append(f"before:{end_date_str.replace('-', '/')}")
        query = " ".join(query_parts) if query_parts else ""

        logger.info(
            f"Gmail query for connector {connector_id}: '{query}' "
            f"(start_date={start_date_str}, end_date={end_date_str})"
        )

        # Use smaller batch size to avoid 413 payload too large errors
        batch_size = 50
        page_token = None
        total_documents_indexed = 0
        total_documents_skipped = 0
        total_messages_fetched = 0
        result_size_estimate = None  # Will be set from first API response

        while total_messages_fetched < max_items:
            # Calculate how many messages to fetch in this batch
            remaining = max_items - total_messages_fetched
            current_batch_size = min(batch_size, remaining)

            # Use result_size_estimate if available, otherwise fall back to max_items
            estimated_total = result_size_estimate if result_size_estimate is not None else max_items
            # Cap estimated_total at max_items to avoid showing misleading progress
            estimated_total = min(estimated_total, max_items)

            await task_logger.log_task_progress(
                log_entry,
                f"Fetching Gmail messages batch via Composio for connector {connector_id} "
                f"({total_messages_fetched}/{estimated_total} fetched, {total_documents_indexed} indexed)",
                {
                    "stage": "fetching_messages",
                    "batch_size": current_batch_size,
                    "total_fetched": total_messages_fetched,
                    "total_indexed": total_documents_indexed,
                    "estimated_total": estimated_total,
                },
            )

            # Fetch batch of messages
            messages, next_token, result_size_estimate_batch, error = await composio_connector.list_gmail_messages(
                query=query,
                max_results=current_batch_size,
                page_token=page_token,
            )

            if error:
                await task_logger.log_task_failure(
                    log_entry, f"Failed to fetch Gmail messages: {error}", {}
                )
                return 0, f"Failed to fetch Gmail messages: {error}"

            if not messages:
                # No more messages available
                break

            # Update result_size_estimate from first response (Gmail provides this estimate)
            if result_size_estimate is None and result_size_estimate_batch is not None:
                result_size_estimate = result_size_estimate_batch
                logger.info(f"Gmail API estimated {result_size_estimate} total messages for query: '{query}'")

            total_messages_fetched += len(messages)
            # Recalculate estimated_total after potentially updating result_size_estimate
            estimated_total = result_size_estimate if result_size_estimate is not None else max_items
            estimated_total = min(estimated_total, max_items)
            
            logger.info(
                f"Fetched batch of {len(messages)} Gmail messages "
                f"(total: {total_messages_fetched}/{estimated_total})"
            )

            # Process batch incrementally
            batch_indexed, batch_skipped = await _process_gmail_message_batch(
                session=session,
                messages=messages,
                composio_connector=composio_connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                total_documents_indexed=total_documents_indexed,
            )

            total_documents_indexed += batch_indexed
            total_documents_skipped += batch_skipped

            logger.info(
                f"Processed batch: {batch_indexed} indexed, {batch_skipped} skipped "
                f"(total: {total_documents_indexed} indexed, {total_documents_skipped} skipped)"
            )

            # Batch commits happen in _process_gmail_message_batch every 10 documents
            # This ensures progress is saved incrementally, preventing data loss on crashes

            # Check if we should continue
            if not next_token:
                # No more pages available
                break

            if len(messages) < current_batch_size:
                # Last page had fewer items than requested, we're done
                break

            # Continue with next page
            page_token = next_token

        if total_messages_fetched == 0:
            success_msg = "No Gmail messages found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"messages_count": 0}
            )
            # CRITICAL: Update timestamp even when no messages found so Electric SQL syncs and UI shows indexed status
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return 0, None  # Return None (not error) when no items found

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted (safety net)
        # This matches the pattern used in non-Composio Gmail indexer
        logger.info(
            f"Final commit: Total {total_documents_indexed} Gmail messages processed"
        )
        await session.commit()
        logger.info(
            "Successfully committed all Composio Gmail document changes to database"
        )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Gmail indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": total_documents_indexed,
                "documents_skipped": total_documents_skipped,
                "messages_fetched": total_messages_fetched,
            },
        )

        return total_documents_indexed, None

    except Exception as e:
        logger.error(f"Failed to index Gmail via Composio: {e!s}", exc_info=True)
        return 0, f"Failed to index Gmail via Composio: {e!s}"


async def _index_composio_google_calendar(
    session: AsyncSession,
    connector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None,
    end_date: str | None,
    task_logger: TaskLoggingService,
    log_entry,
    update_last_indexed: bool = True,
    max_items: int = 2500,
) -> tuple[int, str]:
    """Index Google Calendar events via Composio."""
    try:
        composio_connector = ComposioConnector(session, connector_id)

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Google Calendar events via Composio for connector {connector_id}",
            {"stage": "fetching_events"},
        )

        # Normalize date values - handle "undefined" strings from frontend
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range with defaults (uses last_indexed_at or 365 days back)
        # This ensures indexing works even when user doesn't specify dates
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        # Build time range for API call
        time_min = f"{start_date_str}T00:00:00Z"
        time_max = f"{end_date_str}T23:59:59Z"

        logger.info(
            f"Google Calendar query for connector {connector_id}: "
            f"(start_date={start_date_str}, end_date={end_date_str})"
        )

        events, error = await composio_connector.list_calendar_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_items,
        )

        if error:
            await task_logger.log_task_failure(
                log_entry, f"Failed to fetch Calendar events: {error}", {}
            )
            return 0, f"Failed to fetch Calendar events: {error}"

        if not events:
            success_msg = "No Google Calendar events found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"events_count": 0}
            )
            # CRITICAL: Update timestamp even when no events found so Electric SQL syncs and UI shows indexed status
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return 0, None  # Return None (not error) when no items found - this is success with 0 items

        logger.info(f"Found {len(events)} Google Calendar events to index via Composio")

        documents_indexed = 0
        documents_skipped = 0

        for event in events:
            try:
                # Handle both standard Google API and potential Composio variations
                event_id = event.get("id", "") or event.get("eventId", "")
                summary = event.get("summary", "") or event.get("title", "") or "No Title"

                if not event_id:
                    documents_skipped += 1
                    continue

                # Format to markdown
                markdown_content = composio_connector.format_calendar_event_to_markdown(event)

                # Generate unique identifier
                document_type = DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googlecalendar"])
                unique_identifier_hash = generate_unique_identifier_hash(
                    document_type, f"calendar_{event_id}", search_space_id
                )

                content_hash = generate_content_hash(markdown_content, search_space_id)

                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Extract event times
                start = event.get("start", {})
                end = event.get("end", {})
                start_time = start.get("dateTime") or start.get("date", "")
                end_time = end.get("dateTime") or end.get("date", "")
                location = event.get("location", "")

                if existing_document:
                    if existing_document.content_hash == content_hash:
                        documents_skipped += 1
                        continue

                    # Update existing
                    user_llm = await get_user_long_context_llm(
                        session, user_id, search_space_id
                    )

                    if user_llm:
                        document_metadata = {
                            "event_id": event_id,
                            "summary": summary,
                            "start_time": start_time,
                            "document_type": "Google Calendar Event (Composio)",
                        }
                        summary_content, summary_embedding = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )
                    else:
                        summary_content = f"Calendar: {summary}\n\nStart: {start_time}\nEnd: {end_time}"
                        if location:
                            summary_content += f"\nLocation: {location}"
                        summary_embedding = config.embedding_model_instance.embed(summary_content)

                    chunks = await create_document_chunks(markdown_content)

                    existing_document.title = f"Calendar: {summary}"
                    existing_document.content = summary_content
                    existing_document.content_hash = content_hash
                    existing_document.embedding = summary_embedding
                    existing_document.document_metadata = {
                        "event_id": event_id,
                        "summary": summary,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                        "connector_id": connector_id,
                        "source": "composio",
                    }
                    existing_document.chunks = chunks
                    existing_document.updated_at = get_current_timestamp()

                    documents_indexed += 1
                    
                    # Batch commit every 10 documents 
                    if documents_indexed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_indexed} Google Calendar events processed so far"
                        )
                        await session.commit()
                    continue

                # Create new document
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "event_id": event_id,
                        "summary": summary,
                        "start_time": start_time,
                        "document_type": "Google Calendar Event (Composio)",
                    }
                    summary_content, summary_embedding = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = f"Calendar: {summary}\n\nStart: {start_time}\nEnd: {end_time}"
                    if location:
                        summary_content += f"\nLocation: {location}"
                    summary_embedding = config.embedding_model_instance.embed(summary_content)

                chunks = await create_document_chunks(markdown_content)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Calendar: {summary}",
                    document_type=DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googlecalendar"]),
                    document_metadata={
                        "event_id": event_id,
                        "summary": summary,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                        "connector_id": connector_id,
                        "toolkit_id": "googlecalendar",
                        "source": "composio",
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                    updated_at=get_current_timestamp(),
                )
                session.add(document)
                documents_indexed += 1

                # Batch commit every 10 documents 
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Google Calendar events processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Calendar event: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted (safety net)
        # This matches the pattern used in non-Composio Gmail indexer
        logger.info(
            f"Final commit: Total {documents_indexed} Google Calendar events processed"
        )
        await session.commit()
        logger.info(
            "Successfully committed all Composio Google Calendar document changes to database"
        )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Calendar indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
            },
        )

        return documents_indexed, None

    except Exception as e:
        logger.error(f"Failed to index Google Calendar via Composio: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Calendar via Composio: {e!s}"
