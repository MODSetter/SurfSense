"""
Composio connector indexer.

Routes indexing requests to toolkit-specific handlers (Google Drive, Gmail, Calendar).

Note: This module is intentionally placed in app/tasks/ (not in connector_indexers/)
to avoid circular import issues with the connector_indexers package.
"""

import logging
from datetime import UTC, datetime

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
from app.services.composio_service import INDEXABLE_TOOLKITS
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
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
    session: AsyncSession, connector_id: int, connector_type: SearchSourceConnectorType
) -> SearchSourceConnector | None:
    """Get a connector by ID and type from the database."""
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.connector_type == connector_type,
        )
    )
    return result.scalars().first()


async def update_connector_last_indexed(
    session: AsyncSession,
    connector: SearchSourceConnector,
    update_last_indexed: bool = True,
) -> None:
    """Update the last_indexed_at timestamp for a connector."""
    if update_last_indexed:
        connector.last_indexed_at = datetime.now()
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
        # Get connector by id
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.COMPOSIO_CONNECTOR
        )

        if not connector:
            error_msg = f"Composio connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        # Get toolkit ID from config
        toolkit_id = connector.config.get("toolkit_id")
        if not toolkit_id:
            error_msg = (
                f"Composio connector {connector_id} has no toolkit_id configured"
            )
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
            return 0, success_msg

        logger.info(f"Found {len(all_files)} Google Drive files to index via Composio")

        documents_indexed = 0
        documents_skipped = 0

        for file_info in all_files:
            try:
                # Handle both standard Google API and potential Composio variations
                file_id = file_info.get("id", "") or file_info.get("fileId", "")
                file_name = (
                    file_info.get("name", "")
                    or file_info.get("fileName", "")
                    or "Untitled"
                )
                mime_type = file_info.get("mimeType", "") or file_info.get(
                    "mime_type", ""
                )

                if not file_id:
                    documents_skipped += 1
                    continue

                # Skip folders
                if mime_type == "application/vnd.google-apps.folder":
                    continue

                # Generate unique identifier hash
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.COMPOSIO_CONNECTOR, f"drive_{file_id}", search_space_id
                )

                # Check if document exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Get file content
                (
                    content,
                    content_error,
                ) = await composio_connector.get_drive_file_content(file_id)

                if content_error or not content:
                    logger.warning(
                        f"Could not get content for file {file_name}: {content_error}"
                    )
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
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )
                    else:
                        summary_content = (
                            f"Google Drive File: {file_name}\n\nType: {mime_type}"
                        )
                        summary_embedding = config.embedding_model_instance.embed(
                            summary_content
                        )

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
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = (
                        f"Google Drive File: {file_name}\n\nType: {mime_type}"
                    )
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                chunks = await create_document_chunks(markdown_content)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Drive: {file_name}",
                    document_type=DocumentType.COMPOSIO_CONNECTOR,
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

                if documents_indexed % 10 == 0:
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Drive file: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        if documents_indexed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

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
    """Index Gmail messages via Composio."""
    try:
        composio_connector = ComposioConnector(session, connector_id)

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Gmail messages via Composio for connector {connector_id}",
            {"stage": "fetching_messages"},
        )

        # Build query with date range
        query_parts = []
        if start_date:
            query_parts.append(f"after:{start_date.replace('-', '/')}")
        if end_date:
            query_parts.append(f"before:{end_date.replace('-', '/')}")
        query = " ".join(query_parts)

        messages, error = await composio_connector.list_gmail_messages(
            query=query,
            max_results=max_items,
        )

        if error:
            await task_logger.log_task_failure(
                log_entry, f"Failed to fetch Gmail messages: {error}", {}
            )
            return 0, f"Failed to fetch Gmail messages: {error}"

        if not messages:
            success_msg = "No Gmail messages found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"messages_count": 0}
            )
            return 0, success_msg

        logger.info(f"Found {len(messages)} Gmail messages to index via Composio")

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
                markdown_content = composio_connector.format_gmail_message_to_markdown(
                    message
                )

                # Generate unique identifier
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.COMPOSIO_CONNECTOR,
                    f"gmail_{message_id}",
                    search_space_id,
                )

                content_hash = generate_content_hash(markdown_content, search_space_id)

                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Get label IDs from Composio response
                label_ids = message.get("labelIds", [])

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
                            "subject": subject,
                            "sender": sender,
                            "document_type": "Gmail Message (Composio)",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )
                    else:
                        summary_content = (
                            f"Gmail: {subject}\n\nFrom: {sender}\nDate: {date_str}"
                        )
                        summary_embedding = config.embedding_model_instance.embed(
                            summary_content
                        )

                    chunks = await create_document_chunks(markdown_content)

                    existing_document.title = f"Gmail: {subject}"
                    existing_document.content = summary_content
                    existing_document.content_hash = content_hash
                    existing_document.embedding = summary_embedding
                    existing_document.document_metadata = {
                        "message_id": message_id,
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
                    continue

                # Create new document
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "message_id": message_id,
                        "subject": subject,
                        "sender": sender,
                        "document_type": "Gmail Message (Composio)",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = (
                        f"Gmail: {subject}\n\nFrom: {sender}\nDate: {date_str}"
                    )
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                chunks = await create_document_chunks(markdown_content)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Gmail: {subject}",
                    document_type=DocumentType.COMPOSIO_CONNECTOR,
                    document_metadata={
                        "message_id": message_id,
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

                if documents_indexed % 10 == 0:
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Gmail message: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        if documents_indexed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Gmail indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
            },
        )

        return documents_indexed, None

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
    from datetime import datetime, timedelta

    try:
        composio_connector = ComposioConnector(session, connector_id)

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Google Calendar events via Composio for connector {connector_id}",
            {"stage": "fetching_events"},
        )

        # Build time range
        if start_date:
            time_min = f"{start_date}T00:00:00Z"
        else:
            # Default to 365 days ago
            default_start = datetime.now() - timedelta(days=365)
            time_min = default_start.strftime("%Y-%m-%dT00:00:00Z")

        if end_date:
            time_max = f"{end_date}T23:59:59Z"
        else:
            time_max = datetime.now().strftime("%Y-%m-%dT23:59:59Z")

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
            return 0, success_msg

        logger.info(f"Found {len(events)} Google Calendar events to index via Composio")

        documents_indexed = 0
        documents_skipped = 0

        for event in events:
            try:
                # Handle both standard Google API and potential Composio variations
                event_id = event.get("id", "") or event.get("eventId", "")
                summary = (
                    event.get("summary", "") or event.get("title", "") or "No Title"
                )

                if not event_id:
                    documents_skipped += 1
                    continue

                # Format to markdown
                markdown_content = composio_connector.format_calendar_event_to_markdown(
                    event
                )

                # Generate unique identifier
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.COMPOSIO_CONNECTOR,
                    f"calendar_{event_id}",
                    search_space_id,
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
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )
                    else:
                        summary_content = f"Calendar: {summary}\n\nStart: {start_time}\nEnd: {end_time}"
                        if location:
                            summary_content += f"\nLocation: {location}"
                        summary_embedding = config.embedding_model_instance.embed(
                            summary_content
                        )

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
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    summary_content = (
                        f"Calendar: {summary}\n\nStart: {start_time}\nEnd: {end_time}"
                    )
                    if location:
                        summary_content += f"\nLocation: {location}"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                chunks = await create_document_chunks(markdown_content)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Calendar: {summary}",
                    document_type=DocumentType.COMPOSIO_CONNECTOR,
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

                if documents_indexed % 10 == 0:
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Calendar event: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        if documents_indexed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

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
        logger.error(
            f"Failed to index Google Calendar via Composio: {e!s}", exc_info=True
        )
        return 0, f"Failed to index Google Calendar via Composio: {e!s}"
