"""
Composio Google Calendar Connector Module.

Provides Google Calendar specific methods for data retrieval and indexing via Composio.
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


class ComposioGoogleCalendarConnector(ComposioConnector):
    """
    Google Calendar specific Composio connector.

    Provides methods for listing calendar events and formatting them from
    Google Calendar via Composio.
    """

    async def list_calendar_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 250,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        List Google Calendar events via Composio.

        Args:
            time_min: Start time (RFC3339 format).
            time_max: End time (RFC3339 format).
            max_results: Maximum number of events.

        Returns:
            Tuple of (events list, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_calendar_events(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

    def format_calendar_event_to_markdown(self, event: dict[str, Any]) -> str:
        """
        Format a Google Calendar event to markdown.

        Args:
            event: Event object from Google Calendar API.

        Returns:
            Formatted markdown string.
        """
        try:
            # Extract basic event information
            summary = event.get("summary", "No Title")
            description = event.get("description", "")
            location = event.get("location", "")

            # Extract start and end times
            start = event.get("start", {})
            end = event.get("end", {})

            start_time = start.get("dateTime") or start.get("date", "")
            end_time = end.get("dateTime") or end.get("date", "")

            # Format times for display
            def format_time(time_str: str) -> str:
                if not time_str:
                    return "Unknown"
                try:
                    if "T" in time_str:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        return dt.strftime("%Y-%m-%d %H:%M")
                    return time_str
                except Exception:
                    return time_str

            start_formatted = format_time(start_time)
            end_formatted = format_time(end_time)

            # Extract attendees
            attendees = event.get("attendees", [])
            attendee_list = []
            for attendee in attendees:
                email = attendee.get("email", "")
                display_name = attendee.get("displayName", email)
                response_status = attendee.get("responseStatus", "")
                attendee_list.append(f"- {display_name} ({response_status})")

            # Build markdown content
            markdown_content = f"# {summary}\n\n"
            markdown_content += f"**Start:** {start_formatted}\n"
            markdown_content += f"**End:** {end_formatted}\n"

            if location:
                markdown_content += f"**Location:** {location}\n"

            markdown_content += "\n"

            if description:
                markdown_content += f"## Description\n\n{description}\n\n"

            if attendee_list:
                markdown_content += "## Attendees\n\n"
                markdown_content += "\n".join(attendee_list)
                markdown_content += "\n\n"

            # Add event metadata
            markdown_content += "## Event Details\n\n"
            markdown_content += f"- **Event ID:** {event.get('id', 'Unknown')}\n"
            markdown_content += f"- **Created:** {event.get('created', 'Unknown')}\n"
            markdown_content += f"- **Updated:** {event.get('updated', 'Unknown')}\n"

            return markdown_content

        except Exception as e:
            return f"Error formatting event to markdown: {e!s}"


# ============ Indexer Functions ============


async def index_composio_google_calendar(
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
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str]:
    """Index Google Calendar events via Composio."""
    try:
        composio_connector = ComposioGoogleCalendarConnector(session, connector_id)

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

        # Use provided dates directly if both are provided, otherwise calculate from last_indexed_at
        # This ensures user-selected dates are respected (matching non-Composio Calendar connector behavior)
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
            return (
                0,
                None,
            )  # Return None (not error) when no items found - this is success with 0 items

        logger.info(f"Found {len(events)} Google Calendar events to index via Composio")

        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0  # Track events that failed processing
        duplicate_content_count = (
            0  # Track events skipped due to duplicate content_hash
        )
        last_heartbeat_time = time.time()

        # =======================================================================
        # PHASE 1: Analyze all events, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        events_to_process = []  # List of dicts with document and event data
        new_documents_created = False

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
                        # Ensure status is ready (might have been stuck in processing/pending)
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        documents_skipped += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    events_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "markdown_content": markdown_content,
                            "content_hash": content_hash,
                            "event_id": event_id,
                            "summary": summary,
                            "start_time": start_time,
                            "end_time": end_time,
                            "location": location,
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
                        f"Event {summary} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=summary,
                    document_type=DocumentType(
                        TOOLKIT_TO_DOCUMENT_TYPE["googlecalendar"]
                    ),
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

                events_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "markdown_content": markdown_content,
                        "content_hash": content_hash,
                        "event_id": event_id,
                        "summary": summary,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                    }
                )

            except Exception as e:
                logger.error(f"Error in Phase 1 for event: {e!s}", exc_info=True)
                documents_failed += 1
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([e for e in events_to_process if e['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(events_to_process)} documents")

        for item in events_to_process:
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
                        "event_id": item["event_id"],
                        "summary": item["summary"],
                        "start_time": item["start_time"],
                        "document_type": "Google Calendar Event (Composio)",
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
                    summary_content = (
                        f"Calendar: {item['summary']}\n\n{item['markdown_content']}"
                    )
                    summary_embedding = embed_text(summary_content)

                chunks = await create_document_chunks(item["markdown_content"])

                # Update document to READY with actual content
                document.title = item["summary"]
                document.content = summary_content
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = {
                    "event_id": item["event_id"],
                    "summary": item["summary"],
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "location": item["location"],
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
                        f"Committing batch: {documents_indexed} Google Calendar events processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing Calendar event: {e!s}", exc_info=True)
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

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted (safety net)
        # This matches the pattern used in non-Composio Gmail indexer
        logger.info(
            f"Final commit: Total {documents_indexed} Google Calendar events processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Composio Google Calendar document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same event was indexed by multiple connectors. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
                # Don't fail the entire task - some documents may have been successfully indexed
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
            f"Successfully completed Google Calendar indexing via Composio for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Composio Google Calendar indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return documents_indexed, warning_message

    except Exception as e:
        logger.error(
            f"Failed to index Google Calendar via Composio: {e!s}", exc_info=True
        )
        return 0, f"Failed to index Google Calendar via Composio: {e!s}"
