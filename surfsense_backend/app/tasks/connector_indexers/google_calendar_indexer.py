"""
Google Calendar connector indexer.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_calendar_connector import GoogleCalendarConnector
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
        skipped_events = []
        duplicate_content_count = (
            0  # Track events skipped due to duplicate content_hash
        )

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        for event in events:
            # Check if it's time for a heartbeat update
            if (
                on_heartbeat_callback
                and (time.time() - last_heartbeat_time) >= HEARTBEAT_INTERVAL_SECONDS
            ):
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = time.time()
            try:
                event_id = event.get("id")
                event_summary = event.get("summary", "No Title")
                calendar_id = event.get("calendarId", "")

                if not event_id:
                    logger.warning(f"Skipping event with missing ID: {event_summary}")
                    skipped_events.append(f"{event_summary} (missing ID)")
                    documents_skipped += 1
                    continue

                event_markdown = calendar_client.format_event_to_markdown(event)
                if not event_markdown.strip():
                    logger.warning(f"Skipping event with no content: {event_summary}")
                    skipped_events.append(f"{event_summary} (no content)")
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
                        logger.info(
                            f"Document for Google Calendar event {event_summary} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Google Calendar event {event_summary}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "event_id": event_id,
                                "event_summary": event_summary,
                                "calendar_id": calendar_id,
                                "start_time": start_time,
                                "end_time": end_time,
                                "location": location or "No location",
                                "document_type": "Google Calendar Event",
                                "connector_type": "Google Calendar",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                event_markdown, user_llm, document_metadata
                            )
                        else:
                            summary_content = (
                                f"Google Calendar Event: {event_summary}\n\n"
                            )
                            summary_content += f"Calendar: {calendar_id}\n"
                            summary_content += f"Start: {start_time}\n"
                            summary_content += f"End: {end_time}\n"
                            if location:
                                summary_content += f"Location: {location}\n"
                            if description:
                                desc_preview = description[:1000]
                                if len(description) > 1000:
                                    desc_preview += "..."
                                summary_content += f"Description: {desc_preview}\n"
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(event_markdown)

                        # Update existing document
                        existing_document.title = f"Calendar Event - {event_summary}"
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "event_id": event_id,
                            "event_summary": event_summary,
                            "calendar_id": calendar_id,
                            "start_time": start_time,
                            "end_time": end_time,
                            "location": location,
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        existing_document.chunks = chunks
                        existing_document.updated_at = get_current_timestamp()

                        documents_indexed += 1
                        logger.info(
                            f"Successfully updated Google Calendar event {event_summary}"
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
                    skipped_events.append(
                        f"{event_summary} (already indexed by another connector)"
                    )
                    continue

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "event_id": event_id,
                        "event_summary": event_summary,
                        "calendar_id": calendar_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location or "No location",
                        "document_type": "Google Calendar Event",
                        "connector_type": "Google Calendar",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        event_markdown, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = f"Google Calendar Event: {event_summary}\n\n"
                    summary_content += f"Calendar: {calendar_id}\n"
                    summary_content += f"Start: {start_time}\n"
                    summary_content += f"End: {end_time}\n"
                    if location:
                        summary_content += f"Location: {location}\n"
                    if description:
                        desc_preview = description[:1000]
                        if len(description) > 1000:
                            desc_preview += "..."
                        summary_content += f"Description: {desc_preview}\n"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )
                chunks = await create_document_chunks(event_markdown)

                document = Document(
                    search_space_id=search_space_id,
                    title=f"Calendar Event - {event_summary}",
                    document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
                    document_metadata={
                        "event_id": event_id,
                        "event_summary": event_summary,
                        "calendar_id": calendar_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
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
                logger.info(f"Successfully indexed new event {event_summary}")

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Google Calendar events processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing event {event.get('summary', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_events.append(
                    f"{event.get('summary', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue

        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} Google Calendar events processed"
        )
        try:
            await session.commit()
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

        # Build warning message if duplicates were found
        warning_message = None
        if duplicate_content_count > 0:
            warning_message = f"{duplicate_content_count} skipped (duplicate)"

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Calendar indexing for connector {connector_id}",
            {
                "events_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "duplicate_content_count": duplicate_content_count,
                "skipped_events_count": len(skipped_events),
            },
        )

        logger.info(
            f"Google Calendar indexing completed: {documents_indexed} new events, {documents_skipped} skipped "
            f"({duplicate_content_count} due to duplicate content from other connectors)"
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
