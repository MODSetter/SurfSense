"""
Composio Gmail Connector Module.

Provides Gmail specific methods for data retrieval and indexing via Composio.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.connectors.composio_connector import ComposioConnector
from app.db import Document, DocumentStatus, DocumentType
from app.services.composio_service import TOOLKIT_TO_DOCUMENT_TYPE
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    calculate_date_range,
    check_duplicate_document_by_hash,
    safe_set_chunks,
)
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

# Heartbeat configuration
HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30

logger = logging.getLogger(__name__)


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


async def update_connector_last_indexed(
    session: AsyncSession,
    connector,
    update_last_indexed: bool = True,
) -> None:
    """Update the last_indexed_at timestamp for a connector."""
    if update_last_indexed:
        connector.last_indexed_at = datetime.now(UTC)
        logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")


class ComposioGmailConnector(ComposioConnector):
    """
    Gmail specific Composio connector.

    Provides methods for listing messages, getting message details, and formatting
    Gmail messages from Gmail via Composio.
    """

    async def list_gmail_messages(
        self,
        query: str = "",
        max_results: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int | None, str | None]:
        """
        List Gmail messages via Composio with pagination support.

        Args:
            query: Gmail search query.
            max_results: Maximum number of messages per page (default: 50).
            page_token: Optional pagination token for next page.

        Returns:
            Tuple of (messages list, next_page_token, result_size_estimate, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], None, None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_gmail_messages(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            query=query,
            max_results=max_results,
            page_token=page_token,
        )

    async def get_gmail_message_detail(
        self, message_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get full details of a Gmail message via Composio.

        Args:
            message_id: Gmail message ID.

        Returns:
            Tuple of (message details, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_gmail_message_detail(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            message_id=message_id,
        )

    def format_gmail_message_to_markdown(self, message: dict[str, Any]) -> str:
        """
        Format a Gmail message to markdown.

        Args:
            message: Message object from Composio's GMAIL_FETCH_EMAILS response.
                    Composio structure: messageId, messageText, messageTimestamp,
                    payload.headers, labelIds, attachmentList

        Returns:
            Formatted markdown string.
        """
        try:
            # Composio uses 'messageId' (camelCase)
            message_id = message.get("messageId", "") or message.get("id", "")
            label_ids = message.get("labelIds", [])

            # Extract headers from payload
            payload = message.get("payload", {})
            headers = payload.get("headers", [])

            # Parse headers into a dict
            header_dict = {}
            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                header_dict[name] = value

            # Extract key information
            subject = header_dict.get("subject", "No Subject")
            from_email = header_dict.get("from", "Unknown Sender")
            to_email = header_dict.get("to", "Unknown Recipient")
            # Composio provides messageTimestamp directly
            date_str = message.get("messageTimestamp", "") or header_dict.get(
                "date", "Unknown Date"
            )

            # Build markdown content
            markdown_content = f"# {subject}\n\n"
            markdown_content += f"**From:** {from_email}\n"
            markdown_content += f"**To:** {to_email}\n"
            markdown_content += f"**Date:** {date_str}\n"

            if label_ids:
                markdown_content += f"**Labels:** {', '.join(label_ids)}\n"

            markdown_content += "\n---\n\n"

            # Composio provides full message text in 'messageText'
            message_text = message.get("messageText", "")
            if message_text:
                markdown_content += f"## Content\n\n{message_text}\n\n"
            else:
                # Fallback to snippet if no messageText
                snippet = message.get("snippet", "")
                if snippet:
                    markdown_content += f"## Preview\n\n{snippet}\n\n"

            # Add attachment info if present
            attachments = message.get("attachmentList", [])
            if attachments:
                markdown_content += "## Attachments\n\n"
                for att in attachments:
                    att_name = att.get("filename", att.get("name", "Unknown"))
                    markdown_content += f"- {att_name}\n"
                markdown_content += "\n"

            # Add message metadata
            markdown_content += "## Message Details\n\n"
            markdown_content += f"- **Message ID:** {message_id}\n"

            return markdown_content

        except Exception as e:
            return f"Error formatting message to markdown: {e!s}"


# ============ Indexer Functions ============


async def _analyze_gmail_messages_phase1(
    session: AsyncSession,
    messages: list[dict[str, Any]],
    composio_connector: ComposioGmailConnector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Phase 1: Analyze all messages, create pending documents.
    Makes ALL documents visible in the UI immediately with pending status.

    Returns:
        Tuple of (messages_to_process, documents_skipped, duplicate_content_count)
    """
    messages_to_process = []
    documents_skipped = 0
    duplicate_content_count = 0

    for message in messages:
        try:
            # Composio uses 'messageId' (camelCase), not 'id'
            message_id = message.get("messageId", "") or message.get("id", "")
            if not message_id:
                documents_skipped += 1
                continue

            # Extract message info from Composio response
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

            # Check for empty content
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

            # Get label IDs and thread_id from Composio response
            label_ids = message.get("labelIds", [])
            thread_id = message.get("threadId", "") or message.get("thread_id", "")

            if existing_document:
                if existing_document.content_hash == content_hash:
                    # Ensure status is ready (might have been stuck in processing/pending)
                    if not DocumentStatus.is_state(
                        existing_document.status, DocumentStatus.READY
                    ):
                        existing_document.status = DocumentStatus.ready()
                    documents_skipped += 1
                    continue

                # Queue existing document for update (will be set to processing in Phase 2)
                messages_to_process.append(
                    {
                        "document": existing_document,
                        "is_new": False,
                        "markdown_content": markdown_content,
                        "content_hash": content_hash,
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "subject": subject,
                        "sender": sender,
                        "date_str": date_str,
                        "label_ids": label_ids,
                    }
                )
                continue

            # Document doesn't exist by unique_identifier_hash
            # Check if a document with the same content_hash exists (from standard connector)
            with session.no_autoflush:
                duplicate_by_content = await check_duplicate_document_by_hash(
                    session, content_hash
                )

            if duplicate_by_content:
                logger.info(
                    f"Message {subject} already indexed by another connector "
                    f"(existing document ID: {duplicate_by_content.id}, "
                    f"type: {duplicate_by_content.document_type}). Skipping."
                )
                duplicate_content_count += 1
                documents_skipped += 1
                continue

            # Create new document with PENDING status (visible in UI immediately)
            document = Document(
                search_space_id=search_space_id,
                title=subject,
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

            messages_to_process.append(
                {
                    "document": document,
                    "is_new": True,
                    "markdown_content": markdown_content,
                    "content_hash": content_hash,
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "subject": subject,
                    "sender": sender,
                    "date_str": date_str,
                    "label_ids": label_ids,
                }
            )

        except Exception as e:
            logger.error(f"Error in Phase 1 for message: {e!s}", exc_info=True)
            documents_skipped += 1
            continue

    return messages_to_process, documents_skipped, duplicate_content_count


async def _process_gmail_messages_phase2(
    session: AsyncSession,
    messages_to_process: list[dict[str, Any]],
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int]:
    """
    Phase 2: Process each document one by one.
    Each document transitions: pending → processing → ready/failed

    Returns:
        Tuple of (documents_indexed, documents_failed)
    """
    documents_indexed = 0
    documents_failed = 0
    last_heartbeat_time = time.time()

    for item in messages_to_process:
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

            if user_llm and enable_summary:
                document_metadata_for_summary = {
                    "message_id": item["message_id"],
                    "thread_id": item["thread_id"],
                    "subject": item["subject"],
                    "sender": item["sender"],
                    "document_type": "Gmail Message (Composio)",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    item["markdown_content"], user_llm, document_metadata_for_summary
                )
            else:
                summary_content = f"Gmail: {item['subject']}\n\nFrom: {item['sender']}\nDate: {item['date_str']}\n\n{item['markdown_content']}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(item["markdown_content"])

            # Update document to READY with actual content
            document.title = item["subject"]
            document.content = summary_content
            document.content_hash = item["content_hash"]
            document.embedding = summary_embedding
            document.document_metadata = {
                "message_id": item["message_id"],
                "thread_id": item["thread_id"],
                "subject": item["subject"],
                "sender": item["sender"],
                "date": item["date_str"],
                "labels": item["label_ids"],
                "connector_id": connector_id,
                "source": "composio",
            }
            safe_set_chunks(document, chunks)
            document.updated_at = get_current_timestamp()
            document.status = DocumentStatus.ready()

            documents_indexed += 1

            # Batch commit every 10 documents (for ready status updates)
            if documents_indexed % 10 == 0:
                logger.info(
                    f"Committing batch: {documents_indexed} Gmail messages processed so far"
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Error processing Gmail message: {e!s}", exc_info=True)
            # Mark document as failed with reason (visible in UI)
            try:
                document.status = DocumentStatus.failed(str(e))
                document.updated_at = get_current_timestamp()
            except Exception as status_error:
                logger.error(
                    f"Failed to update document status to failed: {status_error}"
                )
            documents_failed += 1
            continue

    return documents_indexed, documents_failed


async def index_composio_gmail(
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
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str]:
    """Index Gmail messages via Composio with real-time document status updates."""
    try:
        composio_connector = ComposioGmailConnector(session, connector_id)

        # Normalize date values - handle "undefined" strings from frontend
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Use provided dates directly if both are provided, otherwise calculate from last_indexed_at
        if start_date is not None and end_date is not None:
            start_date_str = start_date
            end_date_str = end_date
        else:
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

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Gmail messages via Composio for connector {connector_id}",
            {"stage": "fetching_messages"},
        )

        # =======================================================================
        # FETCH ALL MESSAGES FIRST
        # =======================================================================
        batch_size = 50
        page_token = None
        all_messages = []
        result_size_estimate = None
        last_heartbeat_time = time.time()

        while len(all_messages) < max_items:
            # Send heartbeat periodically
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(len(all_messages))
                    last_heartbeat_time = current_time

            remaining = max_items - len(all_messages)
            current_batch_size = min(batch_size, remaining)

            (
                messages,
                next_token,
                result_size_estimate_batch,
                error,
            ) = await composio_connector.list_gmail_messages(
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
                break

            if result_size_estimate is None and result_size_estimate_batch is not None:
                result_size_estimate = result_size_estimate_batch
                logger.info(
                    f"Gmail API estimated {result_size_estimate} total messages for query: '{query}'"
                )

            all_messages.extend(messages)
            logger.info(
                f"Fetched {len(messages)} messages (total: {len(all_messages)})"
            )

            if not next_token or len(messages) < current_batch_size:
                break

            page_token = next_token

        if not all_messages:
            success_msg = "No Gmail messages found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"messages_count": 0}
            )
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return (
                0,
                None,
            )  # Return None (not error) when no items found - this is success with 0 items

        logger.info(f"Found {len(all_messages)} Gmail messages to index via Composio")

        # =======================================================================
        # PHASE 1: Analyze all messages, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        await task_logger.log_task_progress(
            log_entry,
            f"Phase 1: Creating pending documents for {len(all_messages)} messages",
            {"stage": "phase1_pending"},
        )

        (
            messages_to_process,
            documents_skipped,
            duplicate_content_count,
        ) = await _analyze_gmail_messages_phase1(
            session=session,
            messages=all_messages,
            composio_connector=composio_connector,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
        )

        # Commit all pending documents - they all appear in UI now
        new_documents_count = len([m for m in messages_to_process if m["is_new"]])
        if new_documents_count > 0:
            logger.info(f"Phase 1: Committing {new_documents_count} pending documents")
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(messages_to_process)} documents")
        await task_logger.log_task_progress(
            log_entry,
            f"Phase 2: Processing {len(messages_to_process)} documents",
            {"stage": "phase2_processing"},
        )

        documents_indexed, documents_failed = await _process_gmail_messages_phase2(
            session=session,
            messages_to_process=messages_to_process,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            enable_summary=getattr(connector, "enable_summary", False),
            on_heartbeat_callback=on_heartbeat_callback,
        )

        # CRITICAL: Always update timestamp so Electric SQL syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted
        logger.info(f"Final commit: Total {documents_indexed} Gmail messages processed")
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Composio Gmail document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
            else:
                raise

        # Build warning message if there were issues
        warning_parts = []
        if duplicate_content_count > 0:
            warning_parts.append(f"{duplicate_content_count} duplicate")
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Gmail indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Composio Gmail indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return documents_indexed, warning_message

    except Exception as e:
        logger.error(f"Failed to index Gmail via Composio: {e!s}", exc_info=True)
        return 0, f"Failed to index Gmail via Composio: {e!s}"
