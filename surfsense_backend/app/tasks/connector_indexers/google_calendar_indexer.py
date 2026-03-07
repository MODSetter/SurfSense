"""
Google Calendar connector indexer.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_calendar_connector import GoogleCalendarConnector
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
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    parse_date_flexible,
    safe_set_chunks,
    update_connector_last_indexed,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 30


async def index_google_calendar_events(
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
    Index Google Calendar events.

    Args:
        session: Database session
        connector_id: ID of the Google Calendar connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format). Can be in the past or future.
        end_date: End date for indexing (YYYY-MM-DD format). Can be in the future to index upcoming events.
                  Defaults to today if not provided.
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="google_calendar_events_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Calendar events indexing for connector {connector_id}",
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
            session, connector_id, SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the Google Calendar credentials from the connector config
        config_data = connector.config

        # Decrypt sensitive credentials if encrypted (for backward compatibility)
        from app.config import config
        from app.utils.oauth_security import TokenEncryption

        token_encrypted = config_data.get("_token_encrypted", False)
        if token_encrypted and config.SECRET_KEY:
            try:
                token_encryption = TokenEncryption(config.SECRET_KEY)

                # Decrypt sensitive fields
                if config_data.get("token"):
                    config_data["token"] = token_encryption.decrypt_token(
                        config_data["token"]
                    )
                if config_data.get("refresh_token"):
                    config_data["refresh_token"] = token_encryption.decrypt_token(
                        config_data["refresh_token"]
                    )
                if config_data.get("client_secret"):
                    config_data["client_secret"] = token_encryption.decrypt_token(
                        config_data["client_secret"]
                    )

                logger.info(
                    f"Decrypted Google Calendar credentials for connector {connector_id}"
                )
            except Exception as e:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Failed to decrypt Google Calendar credentials for connector {connector_id}: {e!s}",
                    "Credential decryption failed",
                    {"error_type": "CredentialDecryptionError"},
                )
                return 0, f"Failed to decrypt Google Calendar credentials: {e!s}"

        exp = config_data.get("expiry", "").replace("Z", "")
        credentials = Credentials(
            token=config_data.get("token"),
            refresh_token=config_data.get("refresh_token"),
            token_uri=config_data.get("token_uri"),
            client_id=config_data.get("client_id"),
            client_secret=config_data.get("client_secret"),
            scopes=config_data.get("scopes"),
            expiry=datetime.fromisoformat(exp) if exp else None,
        )

        if (
            not credentials.client_id
            or not credentials.client_secret
            or not credentials.refresh_token
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"Google Calendar credentials not found in connector config for connector {connector_id}",
                "Missing Google Calendar credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Google Calendar credentials not found in connector config"

        # Initialize Google Calendar client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google Calendar client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        calendar_client = GoogleCalendarConnector(
            credentials=credentials,
            session=session,
            user_id=user_id,
            connector_id=connector_id,
        )

        # Handle 'undefined' string from frontend (treat as None)
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range
        # For calendar connectors, allow future dates to index upcoming events
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            # Default to today (users can manually select future dates if needed)
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 30 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Allow future dates - use last_indexed_at as start date
                calculated_start_date = last_indexed_naive
                logger.info(
                    f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                )
            else:
                calculated_start_date = datetime.now() - timedelta(
                    days=365
                )  # Use 365 days as default for calendar events (matches frontend)
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates (including future dates)
            start_date_str = start_date
            end_date_str = end_date

        # FIX: Ensure end_date is at least 1 day after start_date to avoid
        # "start_date must be strictly before end_date" errors when dates are the same
        # (e.g., when last_indexed_at is today)
        if start_date_str == end_date_str:
            logger.info(
                f"Start date ({start_date_str}) equals end date ({end_date_str}), "
                "adjusting end date to next day to ensure valid date range"
            )
            # Parse end_date and add 1 day
            try:
                end_dt = parse_date_flexible(end_date_str)
            except ValueError:
                logger.warning(
                    f"Could not parse end_date '{end_date_str}', using current date"
                )
                end_dt = datetime.now()
            end_dt = end_dt + timedelta(days=1)
            end_date_str = end_dt.strftime("%Y-%m-%d")
            logger.info(f"Adjusted end date to {end_date_str}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Google Calendar events from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_events",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get events within date range from primary calendar
        try:
            events, error = await calendar_client.get_all_primary_calendar_events(
                start_date=start_date_str, end_date=end_date_str
            )

            if error:
                # Don't treat "No events found" as an error that should stop indexing
                if "No events found" in error:
                    logger.info(f"No Google Calendar events found: {error}")
                    logger.info(
                        "No events found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no events found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Google Calendar events found in date range {start_date_str} to {end_date_str}",
                        {"events_found": 0},
                    )
                    return 0, None
                else:
                    logger.error(f"Failed to get Google Calendar events: {error}")
                    # Check if this is an authentication error that requires re-authentication
                    error_message = error
                    error_type = "APIError"
                    if (
                        "re-authenticate" in error.lower()
                        or "expired or been revoked" in error.lower()
                        or "authentication failed" in error.lower()
                    ):
                        error_message = "Google Calendar authentication failed. Please re-authenticate."
                        error_type = "AuthenticationError"

                    await task_logger.log_task_failure(
                        log_entry,
                        error_message,
                        error,
                        {"error_type": error_type},
                    )
                    return 0, error_message

            logger.info(f"Retrieved {len(events)} events from Google Calendar API")

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e!s}", exc_info=True)
            return 0, f"Error fetching Google Calendar events: {e!s}"

        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0  # Track events that failed processing
        duplicate_content_count = (
            0  # Track events skipped due to duplicate content_hash
        )

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        # =======================================================================
        # PHASE 1: Analyze all events, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        events_to_process = []  # List of dicts with document and event data
        new_documents_created = False

        for event in events:
            try:
                event_id = event.get("id")
                event_summary = event.get("summary", "No Title")
                calendar_id = event.get("calendarId", "")

                if not event_id:
                    logger.warning(f"Skipping event with missing ID: {event_summary}")
                    documents_skipped += 1
                    continue

                event_markdown = calendar_client.format_event_to_markdown(event)
                if not event_markdown.strip():
                    logger.warning(f"Skipping event with no content: {event_summary}")
                    documents_skipped += 1
                    continue

                start = event.get("start", {})
                end = event.get("end", {})
                start_time = start.get("dateTime") or start.get("date", "")
                end_time = end.get("dateTime") or end.get("date", "")
                location = event.get("location", "")
                description = event.get("description", "")

                # Generate unique identifier hash for this Google Calendar event
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.GOOGLE_CALENDAR_CONNECTOR, event_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(event_markdown, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if content has changed
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
                            "event_markdown": event_markdown,
                            "content_hash": content_hash,
                            "event_id": event_id,
                            "event_summary": event_summary,
                            "calendar_id": calendar_id,
                            "start_time": start_time,
                            "end_time": end_time,
                            "location": location,
                            "description": description,
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
                    # A document with the same content already exists (likely from Composio connector)
                    logger.info(
                        f"Event {event_summary} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping to avoid duplicate content."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=event_summary,
                    document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
                    document_metadata={
                        "event_id": event_id,
                        "event_summary": event_summary,
                        "calendar_id": calendar_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
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

                events_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "event_markdown": event_markdown,
                        "content_hash": content_hash,
                        "event_id": event_id,
                        "event_summary": event_summary,
                        "calendar_id": calendar_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                        "description": description,
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
                        "event_summary": item["event_summary"],
                        "calendar_id": item["calendar_id"],
                        "start_time": item["start_time"],
                        "end_time": item["end_time"],
                        "location": item["location"] or "No location",
                        "document_type": "Google Calendar Event",
                        "connector_type": "Google Calendar",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        item["event_markdown"], user_llm, document_metadata_for_summary
                    )
                else:
                    summary_content = f"Google Calendar Event: {item['event_summary']}\n\n{item['event_markdown']}"
                    summary_embedding = embed_text(summary_content)

                chunks = await create_document_chunks(item["event_markdown"])

                # Update document to READY with actual content
                document.title = item["event_summary"]
                document.content = summary_content
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = {
                    "event_id": item["event_id"],
                    "event_summary": item["event_summary"],
                    "calendar_id": item["calendar_id"],
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "location": item["location"],
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "connector_id": connector_id,
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
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} Google Calendar events processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Google Calendar document changes to database"
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

        total_processed = documents_indexed

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Calendar indexing for connector {connector_id}",
            {
                "events_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Google Calendar indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return total_processed, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google Calendar indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google Calendar events for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Calendar events: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Calendar events: {e!s}"
