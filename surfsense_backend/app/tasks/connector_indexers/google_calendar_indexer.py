"""
Google Calendar connector indexer.

Uses the shared IndexingPipelineService for document deduplication,
summarization, chunking, and embedding.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_calendar_connector import GoogleCalendarConnector
from app.db import DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.google_credentials import (
    COMPOSIO_GOOGLE_CONNECTOR_TYPES,
    build_composio_credentials,
)

from .base import (
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    parse_date_flexible,
    update_connector_last_indexed,
)

ACCEPTED_CALENDAR_CONNECTOR_TYPES = {
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
}

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _build_connector_doc(
    event: dict,
    event_markdown: str,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Map a raw Google Calendar API event dict to a ConnectorDocument."""
    event_id = event.get("id", "")
    event_summary = event.get("summary", "No Title")
    calendar_id = event.get("calendarId", "")

    start = event.get("start", {})
    end = event.get("end", {})
    start_time = start.get("dateTime") or start.get("date", "")
    end_time = end.get("dateTime") or end.get("date", "")
    location = event.get("location", "")

    metadata = {
        "event_id": event_id,
        "event_summary": event_summary,
        "calendar_id": calendar_id,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "connector_id": connector_id,
        "document_type": "Google Calendar Event",
        "connector_type": "Google Calendar",
    }

    fallback_summary = (
        f"Google Calendar Event: {event_summary}\n\n{event_markdown}"
    )

    return ConnectorDocument(
        title=event_summary,
        source_markdown=event_markdown,
        unique_id=event_id,
        document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_google_calendar_events(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
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
        Tuple containing (number of documents indexed, number of documents skipped, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

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
        # ── Connector lookup ──────────────────────────────────────────
        connector = None
        for ct in ACCEPTED_CALENDAR_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, 0, f"Connector with ID {connector_id} not found"

        # ── Credential building ───────────────────────────────────────
        if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
            connected_account_id = connector.config.get("composio_connected_account_id")
            if not connected_account_id:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Composio connected_account_id not found for connector {connector_id}",
                    "Missing Composio account",
                    {"error_type": "MissingComposioAccount"},
                )
                return 0, 0, "Composio connected_account_id not found"
            credentials = build_composio_credentials(connected_account_id)
        else:
            config_data = connector.config

            from app.config import config
            from app.utils.oauth_security import TokenEncryption

            token_encrypted = config_data.get("_token_encrypted", False)
            if token_encrypted and config.SECRET_KEY:
                try:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
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
                    return 0, 0, f"Failed to decrypt Google Calendar credentials: {e!s}"

            exp = config_data.get("expiry", "")
            if exp:
                exp = exp.replace("Z", "")
            credentials = Credentials(
                token=config_data.get("token"),
                refresh_token=config_data.get("refresh_token"),
                token_uri=config_data.get("token_uri"),
                client_id=config_data.get("client_id"),
                client_secret=config_data.get("client_secret"),
                scopes=config_data.get("scopes", []),
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
                return 0, 0, "Google Calendar credentials not found in connector config"

        # ── Calendar client init ──────────────────────────────────────
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

        # ── Date range calculation ────────────────────────────────────
        if start_date is None or end_date is None:
            calculated_end_date = datetime.now()

            if connector.last_indexed_at:
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )
                calculated_start_date = last_indexed_naive
                logger.info(
                    f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                )
            else:
                calculated_start_date = datetime.now() - timedelta(days=365)
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            start_date_str = start_date
            end_date_str = end_date

        if start_date_str == end_date_str:
            logger.info(
                f"Start date ({start_date_str}) equals end date ({end_date_str}), "
                "adjusting end date to next day to ensure valid date range"
            )
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

        # ── Fetch events ──────────────────────────────────────────────
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Google Calendar events from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_events",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        try:
            events, error = await calendar_client.get_all_primary_calendar_events(
                start_date=start_date_str, end_date=end_date_str
            )

            if error:
                if "No events found" in error:
                    logger.info(f"No Google Calendar events found: {error}")
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Google Calendar events found in date range {start_date_str} to {end_date_str}",
                        {"events_found": 0},
                    )
                    return 0, 0, None
                else:
                    logger.error(f"Failed to get Google Calendar events: {error}")
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
                    return 0, 0, error_message

            logger.info(f"Retrieved {len(events)} events from Google Calendar API")

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e!s}", exc_info=True)
            return 0, 0, f"Error fetching Google Calendar events: {e!s}"

        # ── Build ConnectorDocuments ──────────────────────────────────
        connector_docs: list[ConnectorDocument] = []
        documents_skipped = 0
        duplicate_content_count = 0

        for event in events:
            try:
                event_id = event.get("id")
                event_summary = event.get("summary", "No Title")

                if not event_id:
                    logger.warning(f"Skipping event with missing ID: {event_summary}")
                    documents_skipped += 1
                    continue

                event_markdown = calendar_client.format_event_to_markdown(event)
                if not event_markdown.strip():
                    logger.warning(f"Skipping event with no content: {event_summary}")
                    documents_skipped += 1
                    continue

                doc = _build_connector_doc(
                    event,
                    event_markdown,
                    connector_id=connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    enable_summary=connector.enable_summary,
                )

                with session.no_autoflush:
                    duplicate = await check_duplicate_document_by_hash(
                        session, compute_content_hash(doc)
                    )
                if duplicate:
                    logger.info(
                        f"Event {doc.title} already indexed by another connector "
                        f"(existing document ID: {duplicate.id}, "
                        f"type: {duplicate.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                connector_docs.append(doc)

            except Exception as e:
                logger.error(f"Error building ConnectorDocument for event: {e!s}", exc_info=True)
                documents_skipped += 1
                continue

        # ── Pipeline: migrate legacy docs + parallel index ─────────────
        pipeline = IndexingPipelineService(session)

        await pipeline.migrate_legacy_docs(connector_docs)

        async def _get_llm(s):
            return await get_user_long_context_llm(s, user_id, search_space_id)

        _, documents_indexed, documents_failed = await pipeline.index_batch_parallel(
            connector_docs,
            _get_llm,
            max_concurrency=3,
            on_heartbeat=on_heartbeat_callback,
            heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
        )

        # ── Finalize ──────────────────────────────────────────────────
        await update_connector_last_indexed(session, connector, update_last_indexed)

        logger.info(
            f"Final commit: Total {documents_indexed} Google Calendar events processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Google Calendar document changes to database"
            )
        except Exception as e:
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
        return total_processed, documents_skipped, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google Calendar indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google Calendar events for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Calendar events: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Google Calendar events: {e!s}"
