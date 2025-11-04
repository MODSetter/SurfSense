"""
Google Calendar connector indexer.
"""

from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
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
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_google_calendar_events(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Google Calendar events.

    Args:
        session: Database session
        connector_id: ID of the Google Calendar connector
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
        exp = connector.config.get("expiry").replace("Z", "")
        credentials = Credentials(
            token=connector.config.get("token"),
            refresh_token=connector.config.get("refresh_token"),
            token_uri=connector.config.get("token_uri"),
            client_id=connector.config.get("client_id"),
            client_secret=connector.config.get("client_secret"),
            scopes=connector.config.get("scopes"),
            expiry=datetime.fromisoformat(exp),
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

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 30 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(
                        f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 30 days ago instead."
                    )
                    calculated_start_date = calculated_end_date - timedelta(days=30)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(
                        f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                    )
            else:
                calculated_start_date = calculated_end_date - timedelta(
                    days=30
                )  # Use 30 days as default for calendar events
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (30 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates
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
                logger.error(f"Failed to get Google Calendar events: {error}")

                # Don't treat "No events found" as an error that should stop indexing
                if "No events found" in error:
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
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Google Calendar events: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Google Calendar events: {error}"

            logger.info(f"Retrieved {len(events)} events from Google Calendar API")

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e!s}", exc_info=True)
            return 0, f"Error fetching Google Calendar events: {e!s}"

        documents_indexed = 0
        documents_skipped = 0
        skipped_events = []

        for event in events:
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

                        documents_indexed += 1
                        logger.info(
                            f"Successfully updated Google Calendar event {event_summary}"
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
        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Calendar indexing for connector {connector_id}",
            {
                "events_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_events_count": len(skipped_events),
            },
        )

        logger.info(
            f"Google Calendar indexing completed: {documents_indexed} new events, {documents_skipped} skipped"
        )
        return total_processed, None

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
