"""
Google Gmail connector indexer.
"""

from datetime import datetime

from google.oauth2.credentials import Credentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.google_gmail_connector import GoogleGmailConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnectorType,
)
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


async def index_google_gmail_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    max_messages: int = 1000,
) -> tuple[int, str]:
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
        max_messages: Maximum number of messages to fetch (default: 100)

    Returns:
        Tuple of (number_of_indexed_messages, status_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
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
        # Get connector by id
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR
        )

        if not connector:
            error_msg = f"Gmail connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        # Create credentials from connector config
        config_data = connector.config
        exp = config_data.get("expiry").replace("Z", "")
        credentials = Credentials(
            token=config_data.get("token"),
            refresh_token=config_data.get("refresh_token"),
            token_uri=config_data.get("token_uri"),
            client_id=config_data.get("client_id"),
            client_secret=config_data.get("client_secret"),
            scopes=config_data.get("scopes", []),
            expiry=datetime.fromisoformat(exp),
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
            return 0, "Google gmail credentials not found in connector config"

        # Initialize Google gmail client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google gmail client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        # Initialize Google gmail connector
        gmail_connector = GoogleGmailConnector(
            credentials, session, user_id, connector_id
        )

        # Fetch recent Google gmail messages
        logger.info(f"Fetching recent emails for connector {connector_id}")
        messages, error = await gmail_connector.get_recent_messages(
            max_results=max_messages, start_date=start_date, end_date=end_date
        )

        if error:
            await task_logger.log_task_failure(
                log_entry, f"Failed to fetch messages: {error}", {}
            )
            return 0, f"Failed to fetch Gmail messages: {error}"

        if not messages:
            success_msg = "No Google gmail messages found in the specified date range"
            await task_logger.log_task_success(
                log_entry, success_msg, {"messages_count": 0}
            )
            return 0, success_msg

        logger.info(f"Found {len(messages)} Google gmail messages to index")

        documents_indexed = 0
        skipped_messages = []
        documents_skipped = 0
        for message in messages:
            try:
                # Extract message information
                message_id = message.get("id", "")
                thread_id = message.get("threadId", "")

                # Extract headers for subject and sender
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

                if not message_id:
                    logger.warning(f"Skipping message with missing ID: {subject}")
                    skipped_messages.append(f"{subject} (missing ID)")
                    documents_skipped += 1
                    continue

                # Format message to markdown
                markdown_content = gmail_connector.format_message_to_markdown(message)

                if not markdown_content.strip():
                    logger.warning(f"Skipping message with no content: {subject}")
                    skipped_messages.append(f"{subject} (no content)")
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this Gmail message
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.GOOGLE_GMAIL_CONNECTOR, message_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(markdown_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for Gmail message {subject} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Gmail message {subject}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "message_id": message_id,
                                "thread_id": thread_id,
                                "subject": subject,
                                "sender": sender,
                                "date": date_str,
                                "document_type": "Gmail Message",
                                "connector_type": "Google Gmail",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                markdown_content, user_llm, document_metadata
                            )
                        else:
                            summary_content = f"Google Gmail Message: {subject}\n\n"
                            summary_content += f"Sender: {sender}\n"
                            summary_content += f"Date: {date_str}\n"
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(markdown_content)

                        # Update existing document
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
                            "connector_id": connector_id,
                        }
                        existing_document.chunks = chunks

                        documents_indexed += 1
                        logger.info(f"Successfully updated Gmail message {subject}")
                        continue

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "subject": subject,
                        "sender": sender,
                        "date": date_str,
                        "document_type": "Gmail Message",
                        "connector_type": "Google Gmail",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        markdown_content, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = f"Google Gmail Message: {subject}\n\n"
                    summary_content += f"Sender: {sender}\n"
                    summary_content += f"Date: {date_str}\n"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                # Process chunks
                chunks = await create_document_chunks(markdown_content)

                # Create and store new document
                logger.info(f"Creating new document for Gmail message: {subject}")
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Gmail: {subject}",
                    document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
                    document_metadata={
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "subject": subject,
                        "sender": sender,
                        "date": date_str,
                        "connector_id": connector_id,
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )
                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new email {summary_content}")

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Gmail messages processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing the email {message_id}: {e!s}",
                    exc_info=True,
                )
                skipped_messages.append(f"{subject} (processing error)")
                documents_skipped += 1
                continue  # Skip this message and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_indexed} Gmail messages processed")
        await session.commit()
        logger.info(
            "Successfully committed all Google gmail document changes to database"
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google gmail indexing for connector {connector_id}",
            {
                "events_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_messages_count": len(skipped_messages),
            },
        )

        logger.info(
            f"Google gmail indexing completed: {documents_indexed} new emails, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google gmail indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google gmail emails for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google gmail emails: {e!s}", exc_info=True)
        return 0, f"Failed to index Google gmail emails: {e!s}"
