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

from app.config import config
from app.connectors.composio_connector import ComposioConnector
from app.db import Document, DocumentType
from app.services.composio_service import TOOLKIT_TO_DOCUMENT_TYPE
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import calculate_date_range
from app.utils.document_converters import (
    create_document_chunks,
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


async def _process_gmail_message_batch(
    session: AsyncSession,
    messages: list[dict[str, Any]],
    composio_connector: ComposioGmailConnector,
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
            markdown_content = composio_connector.format_gmail_message_to_markdown(
                message
            )

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
                created_by_id=user_id,
                connector_id=connector_id,
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
                logger.error(
                    f"Error during rollback: {rollback_error!s}", exc_info=True
                )
            continue

    return documents_indexed, documents_skipped


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
    """Index Gmail messages via Composio with pagination and incremental processing."""
    try:
        composio_connector = ComposioGmailConnector(session, connector_id)

        # Normalize date values - handle "undefined" strings from frontend
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Use provided dates directly if both are provided, otherwise calculate from last_indexed_at
        # This ensures user-selected dates are respected (matching non-Composio Gmail connector behavior)
        if start_date is not None and end_date is not None:
            # User provided both dates - use them directly
            start_date_str = start_date
            end_date_str = end_date
        else:
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
        last_heartbeat_time = time.time()

        while total_messages_fetched < max_items:
            # Send heartbeat periodically to indicate task is still alive
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(total_documents_indexed)
                    last_heartbeat_time = current_time

            # Calculate how many messages to fetch in this batch
            remaining = max_items - total_messages_fetched
            current_batch_size = min(batch_size, remaining)

            # Use result_size_estimate if available, otherwise fall back to max_items
            estimated_total = (
                result_size_estimate if result_size_estimate is not None else max_items
            )
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
                # No more messages available
                break

            # Update result_size_estimate from first response (Gmail provides this estimate)
            if result_size_estimate is None and result_size_estimate_batch is not None:
                result_size_estimate = result_size_estimate_batch
                logger.info(
                    f"Gmail API estimated {result_size_estimate} total messages for query: '{query}'"
                )

            total_messages_fetched += len(messages)
            # Recalculate estimated_total after potentially updating result_size_estimate
            estimated_total = (
                result_size_estimate if result_size_estimate is not None else max_items
            )
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
