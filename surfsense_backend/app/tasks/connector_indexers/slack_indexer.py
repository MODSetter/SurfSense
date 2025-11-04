"""
Slack connector indexer.
"""

from datetime import datetime

from slack_sdk.errors import SlackApiError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.slack_history import SlackHistory
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    build_document_metadata_markdown,
    calculate_date_range,
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_slack_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Slack messages from all accessible channels.

    Args:
        session: Database session
        connector_id: ID of the Slack connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="slack_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Slack messages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Slack connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.SLACK_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Slack connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Slack connector",
            )

        # Get the Slack token from the connector config
        slack_token = connector.config.get("SLACK_BOT_TOKEN")
        if not slack_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Slack token not found in connector config for connector {connector_id}",
                "Missing Slack token",
                {"error_type": "MissingToken"},
            )
            return 0, "Slack token not found in connector config"

        # Initialize Slack client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Slack client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        slack_client = SlackHistory(token=slack_token)

        # Calculate date range
        await task_logger.log_task_progress(
            log_entry,
            "Calculating date range for Slack indexing",
            {
                "stage": "date_calculation",
                "provided_start_date": start_date,
                "provided_end_date": end_date,
            },
        )

        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        logger.info(f"Indexing Slack messages from {start_date_str} to {end_date_str}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Slack channels from {start_date_str} to {end_date_str}",
            {
                "stage": "fetch_channels",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get all channels
        try:
            channels = slack_client.get_all_channels()
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Slack channels for connector {connector_id}",
                str(e),
                {"error_type": "ChannelFetchError"},
            )
            return 0, f"Failed to get Slack channels: {e!s}"

        if not channels:
            await task_logger.log_task_success(
                log_entry,
                f"No Slack channels found for connector {connector_id}",
                {"channels_found": 0},
            )
            return 0, "No Slack channels found"

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(channels)} Slack channels",
            {"stage": "process_channels", "total_channels": len(channels)},
        )

        # Process each channel
        for channel_obj in channels:
            channel_id = channel_obj["id"]
            channel_name = channel_obj["name"]
            is_private = channel_obj["is_private"]
            is_member = channel_obj["is_member"]

            try:
                # If it's a private channel and the bot is not a member, skip.
                if is_private and not is_member:
                    logger.warning(
                        f"Bot is not a member of private channel {channel_name} ({channel_id}). Skipping."
                    )
                    skipped_channels.append(
                        f"{channel_name} (private, bot not a member)"
                    )
                    documents_skipped += 1
                    continue

                # Get messages for this channel
                messages, error = slack_client.get_history_by_date_range(
                    channel_id=channel_id,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    limit=1000,  # Limit to 1000 messages per channel
                )

                if error:
                    logger.warning(
                        f"Error getting messages from channel {channel_name}: {error}"
                    )
                    skipped_channels.append(f"{channel_name} (error: {error})")
                    documents_skipped += 1
                    continue  # Skip this channel if there's an error

                if not messages:
                    logger.info(
                        f"No messages found in channel {channel_name} for the specified date range."
                    )
                    documents_skipped += 1
                    continue  # Skip if no messages

                # Format messages with user info
                formatted_messages = []
                for msg in messages:
                    # Skip bot messages and system messages
                    if msg.get("subtype") in [
                        "bot_message",
                        "channel_join",
                        "channel_leave",
                    ]:
                        continue

                    formatted_msg = slack_client.format_message(
                        msg, include_user_info=True
                    )
                    formatted_messages.append(formatted_msg)

                if not formatted_messages:
                    logger.info(
                        f"No valid messages found in channel {channel_name} after filtering."
                    )
                    documents_skipped += 1
                    continue  # Skip if no valid messages after filtering

                for msg in formatted_messages:
                    timestamp = msg.get("datetime", "Unknown Time")
                    msg_ts = msg.get("ts", timestamp)  # Get original Slack timestamp
                    msg_user_name = msg.get("user_name", "Unknown User")
                    msg_user_email = msg.get("user_email", "Unknown Email")
                    msg_text = msg.get("text", "")

                    # Format document metadata
                    metadata_sections = [
                        (
                            "METADATA",
                            [
                                f"CHANNEL_NAME: {channel_name}",
                                f"CHANNEL_ID: {channel_id}",
                                f"MESSAGE_TIMESTAMP: {timestamp}",
                                f"MESSAGE_USER_NAME: {msg_user_name}",
                                f"MESSAGE_USER_EMAIL: {msg_user_email}",
                            ],
                        ),
                        (
                            "CONTENT",
                            ["FORMAT: markdown", "TEXT_START", msg_text, "TEXT_END"],
                        ),
                    ]

                    # Build the document string
                    combined_document_string = build_document_metadata_markdown(
                        metadata_sections
                    )

                    # Generate unique identifier hash for this Slack message
                    unique_identifier = f"{channel_id}_{msg_ts}"
                    unique_identifier_hash = generate_unique_identifier_hash(
                        DocumentType.SLACK_CONNECTOR, unique_identifier, search_space_id
                    )

                    # Generate content hash
                    content_hash = generate_content_hash(
                        combined_document_string, search_space_id
                    )

                    # Check if document with this unique identifier already exists
                    existing_document = await check_document_by_unique_identifier(
                        session, unique_identifier_hash
                    )

                    if existing_document:
                        # Document exists - check if content has changed
                        if existing_document.content_hash == content_hash:
                            logger.info(
                                f"Document for Slack message {msg_ts} in channel {channel_name} unchanged. Skipping."
                            )
                            documents_skipped += 1
                            continue
                        else:
                            # Content has changed - update the existing document
                            logger.info(
                                f"Content changed for Slack message {msg_ts} in channel {channel_name}. Updating document."
                            )

                            # Update chunks and embedding
                            chunks = await create_document_chunks(
                                combined_document_string
                            )
                            doc_embedding = config.embedding_model_instance.embed(
                                combined_document_string
                            )

                            # Update existing document
                            existing_document.content = combined_document_string
                            existing_document.content_hash = content_hash
                            existing_document.embedding = doc_embedding
                            existing_document.document_metadata = {
                                "channel_name": channel_name,
                                "channel_id": channel_id,
                                "start_date": start_date_str,
                                "end_date": end_date_str,
                                "message_count": len(formatted_messages),
                                "indexed_at": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }

                            # Delete old chunks and add new ones
                            existing_document.chunks = chunks

                            documents_indexed += 1
                            logger.info(f"Successfully updated Slack message {msg_ts}")
                            continue

                    # Document doesn't exist - create new one
                    # Process chunks
                    chunks = await create_document_chunks(combined_document_string)
                    doc_embedding = config.embedding_model_instance.embed(
                        combined_document_string
                    )

                    # Create and store new document
                    document = Document(
                        search_space_id=search_space_id,
                        title=f"Slack - {channel_name}",
                        document_type=DocumentType.SLACK_CONNECTOR,
                        document_metadata={
                            "channel_name": channel_name,
                            "channel_id": channel_id,
                            "start_date": start_date_str,
                            "end_date": end_date_str,
                            "message_count": len(formatted_messages),
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        content=combined_document_string,
                        embedding=doc_embedding,
                        chunks=chunks,
                        content_hash=content_hash,
                        unique_identifier_hash=unique_identifier_hash,
                    )

                    session.add(document)
                    documents_indexed += 1

                    # Batch commit every 10 documents
                    if documents_indexed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_indexed} Slack channels processed so far"
                        )
                        await session.commit()

                logger.info(
                    f"Successfully indexed new channel {channel_name} with {len(formatted_messages)} messages"
                )

            except SlackApiError as slack_error:
                logger.error(
                    f"Slack API error for channel {channel_name}: {slack_error!s}"
                )
                skipped_channels.append(f"{channel_name} (Slack API error)")
                documents_skipped += 1
                continue  # Skip this channel and continue with others
            except Exception as e:
                logger.error(f"Error processing channel {channel_name}: {e!s}")
                skipped_channels.append(f"{channel_name} (processing error)")
                documents_skipped += 1
                continue  # Skip this channel and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        # and if we successfully indexed at least one channel
        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_indexed} Slack channels processed")
        await session.commit()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {total_processed} channels. Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {total_processed} channels."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Slack indexing for connector {connector_id}",
            {
                "channels_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_channels_count": len(skipped_channels),
                "result_message": result_message,
            },
        )

        logger.info(
            f"Slack indexing completed: {documents_indexed} new channels, {documents_skipped} skipped"
        )
        return total_processed, result_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Slack indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}")
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Slack messages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Slack messages: {e!s}")
        return 0, f"Failed to index Slack messages: {e!s}"
