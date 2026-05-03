"""
Google Gmail connector indexer.

Uses the shared IndexingPipelineService for document deduplication,
summarization, chunking, and embedding.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_gmail_connector import GoogleGmailConnector
from app.db import DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)
from app.services.composio_service import ComposioService
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.google_credentials import COMPOSIO_GOOGLE_CONNECTOR_TYPES

from .base import (
    calculate_date_range,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)

ACCEPTED_GMAIL_CONNECTOR_TYPES = {
    SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
}

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _normalize_composio_gmail_message(message: dict) -> dict:
    if message.get("payload"):
        return message

    headers = []
    header_values = {
        "Subject": message.get("subject"),
        "From": message.get("from") or message.get("sender"),
        "To": message.get("to") or message.get("recipient"),
        "Date": message.get("date"),
    }
    for name, value in header_values.items():
        if value:
            headers.append({"name": name, "value": value})

    return {
        **message,
        "id": message.get("id")
        or message.get("message_id")
        or message.get("messageId"),
        "threadId": message.get("threadId") or message.get("thread_id"),
        "payload": {"headers": headers},
        "snippet": message.get("snippet", ""),
        "messageText": message.get("messageText") or message.get("body") or "",
    }


def _format_gmail_message_to_markdown(message: dict) -> str:
    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in message.get("payload", {}).get("headers", [])
        if isinstance(header, dict)
    }
    subject = headers.get("subject", "No Subject")
    from_email = headers.get("from", "Unknown Sender")
    to_email = headers.get("to", "Unknown Recipient")
    date_str = headers.get("date", "Unknown Date")
    message_text = (
        message.get("messageText")
        or message.get("body")
        or message.get("text")
        or message.get("snippet", "")
    )

    return (
        f"# {subject}\n\n"
        f"**From:** {from_email}\n"
        f"**To:** {to_email}\n"
        f"**Date:** {date_str}\n\n"
        f"## Message Content\n\n{message_text}\n\n"
        f"## Message Details\n\n"
        f"- **Message ID:** {message.get('id', 'Unknown')}\n"
        f"- **Thread ID:** {message.get('threadId', 'Unknown')}\n"
    )


def _build_connector_doc(
    message: dict,
    markdown_content: str,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Map a raw Gmail API message dict to a ConnectorDocument."""
    message_id = message.get("id", "")
    thread_id = message.get("threadId", "")
    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    subject = "No Subject"
    sender = "Unknown Sender"
    date_str = "Unknown Date"

    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        if name == "subject":
            subject = value
        elif name == "from":
            sender = value
        elif name == "date":
            date_str = value

    metadata = {
        "message_id": message_id,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "date": date_str,
        "connector_id": connector_id,
        "document_type": "Gmail Message",
        "connector_type": "Google Gmail",
    }

    fallback_summary = (
        f"Google Gmail Message: {subject}\n\n"
        f"From: {sender}\nDate: {date_str}\n\n"
        f"{markdown_content}"
    )

    return ConnectorDocument(
        title=subject,
        source_markdown=markdown_content,
        unique_id=message_id,
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_google_gmail_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    max_messages: int = 1000,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """
    Index Gmail messages for a specific connector.

    Args:
        session: Database session
        connector_id: ID of the Gmail connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for filtering messages (YYYY-MM-DD format)
        end_date: End date for filtering messages (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        max_messages: Maximum number of messages to fetch (default: 1000)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple of (number_of_indexed_messages, number_of_skipped_messages, status_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    log_entry = await task_logger.log_task_start(
        task_name="google_gmail_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Gmail messages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "max_messages": max_messages,
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # ── Connector lookup ──────────────────────────────────────────
        connector = None
        for ct in ACCEPTED_GMAIL_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break

        if not connector:
            error_msg = f"Gmail connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, error_msg

        is_composio_connector = (
            connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES
        )
        gmail_connector = None
        composio_service = None
        connected_account_id = None

        # ── Credential/client building ────────────────────────────────
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
            composio_service = ComposioService()
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
                        f"Decrypted Google Gmail credentials for connector {connector_id}"
                    )
                except Exception as e:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to decrypt Google Gmail credentials for connector {connector_id}: {e!s}",
                        "Credential decryption failed",
                        {"error_type": "CredentialDecryptionError"},
                    )
                    return 0, 0, f"Failed to decrypt Google Gmail credentials: {e!s}"

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
                    f"Google gmail credentials not found in connector config for connector {connector_id}",
                    "Missing Google gmail credentials",
                    {"error_type": "MissingCredentials"},
                )
                return 0, 0, "Google gmail credentials not found in connector config"

        # ── Gmail client init ─────────────────────────────────────────
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google gmail client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        if not is_composio_connector:
            gmail_connector = GoogleGmailConnector(
                credentials, session, user_id, connector_id
            )

        calculated_start_date, calculated_end_date = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        # ── Fetch messages ────────────────────────────────────────────
        logger.info(
            f"Fetching emails for connector {connector_id} "
            f"from {calculated_start_date} to {calculated_end_date}"
        )
        if is_composio_connector:
            query_parts = []
            if calculated_start_date:
                query_parts.append(f"after:{calculated_start_date.replace('-', '/')}")
            if calculated_end_date:
                query_parts.append(f"before:{calculated_end_date.replace('-', '/')}")
            query = " ".join(query_parts)

            messages = []
            page_token = None
            error = None
            while len(messages) < max_messages:
                page_size = min(50, max_messages - len(messages))
                (
                    page_messages,
                    page_token,
                    _estimate,
                    page_error,
                ) = await composio_service.get_gmail_messages(
                    connected_account_id=connected_account_id,
                    entity_id=f"surfsense_{user_id}",
                    query=query,
                    max_results=page_size,
                    page_token=page_token,
                )
                if page_error:
                    error = page_error
                    break
                for page_message in page_messages:
                    message_id = (
                        page_message.get("id")
                        or page_message.get("message_id")
                        or page_message.get("messageId")
                    )
                    if message_id:
                        (
                            detail,
                            detail_error,
                        ) = await composio_service.get_gmail_message_detail(
                            connected_account_id=connected_account_id,
                            entity_id=f"surfsense_{user_id}",
                            message_id=message_id,
                        )
                        if not detail_error and isinstance(detail, dict):
                            page_message = detail
                    messages.append(_normalize_composio_gmail_message(page_message))
                if not page_token:
                    break
        else:
            messages, error = await gmail_connector.get_recent_messages(
                max_results=max_messages,
                start_date=calculated_start_date,
                end_date=calculated_end_date,
            )

        if error:
            error_message = error
            error_type = "APIError"
            if (
                "re-authenticate" in error.lower()
                or "expired or been revoked" in error.lower()
                or "authentication failed" in error.lower()
            ):
                error_message = "Gmail authentication failed. Please re-authenticate."
                error_type = "AuthenticationError"

            await task_logger.log_task_failure(
                log_entry, error_message, error, {"error_type": error_type}
            )
            return 0, 0, error_message

        if not messages:
            success_msg = "No Google gmail messages found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"messages_count": 0}
            )
            return 0, 0, success_msg

        logger.info(f"Found {len(messages)} Google gmail messages to index")

        # ── Create placeholders for instant UI feedback ───────────────
        pipeline = IndexingPipelineService(session)

        def _gmail_subject(msg: dict) -> str:
            for h in msg.get("payload", {}).get("headers", []):
                if h.get("name", "").lower() == "subject":
                    return h.get("value", "No Subject")
            return "No Subject"

        placeholders = [
            PlaceholderInfo(
                title=_gmail_subject(msg),
                document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
                unique_id=msg.get("id", ""),
                search_space_id=search_space_id,
                connector_id=connector_id,
                created_by_id=user_id,
                metadata={
                    "message_id": msg.get("id", ""),
                    "connector_id": connector_id,
                    "connector_type": "Google Gmail",
                },
            )
            for msg in messages
            if msg.get("id")
        ]
        await pipeline.create_placeholder_documents(placeholders)

        # ── Build ConnectorDocuments ──────────────────────────────────
        connector_docs: list[ConnectorDocument] = []
        documents_skipped = 0
        duplicate_content_count = 0

        for message in messages:
            try:
                message_id = message.get("id", "")
                if not message_id:
                    logger.warning("Skipping message with missing ID")
                    documents_skipped += 1
                    continue

                if is_composio_connector:
                    markdown_content = _format_gmail_message_to_markdown(message)
                else:
                    markdown_content = gmail_connector.format_message_to_markdown(
                        message
                    )
                if not markdown_content.strip():
                    logger.warning(f"Skipping message with no content: {message_id}")
                    documents_skipped += 1
                    continue

                doc = _build_connector_doc(
                    message,
                    markdown_content,
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
                        f"Gmail message {doc.title} already indexed by another connector "
                        f"(existing document ID: {duplicate.id}, "
                        f"type: {duplicate.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                connector_docs.append(doc)

            except Exception as e:
                logger.error(
                    f"Error building ConnectorDocument for message: {e!s}",
                    exc_info=True,
                )
                documents_skipped += 1
                continue

        # ── Pipeline: migrate legacy docs + parallel index ─────────────
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

        logger.info(f"Final commit: Total {documents_indexed} Gmail messages processed")
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Google Gmail document changes to database"
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
            f"Successfully completed Google Gmail indexing for connector {connector_id}",
            {
                "events_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Google Gmail indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return total_processed, documents_skipped, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google gmail indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google gmail emails for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google gmail emails: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Google gmail emails: {e!s}"
