"""
Slack connector indexer.

Implements batch indexing: groups up to SLACK_BATCH_SIZE messages per channel
into a single document for efficient indexing and better conversational context.

Uses 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from slack_sdk.errors import SlackApiError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.slack_history import SlackHistory
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    build_document_metadata_markdown,
    calculate_date_range,
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    safe_set_chunks,
    update_connector_last_indexed,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds - update notification every 30 seconds
HEARTBEAT_INTERVAL_SECONDS = 30

# Number of messages to combine into a single document for batch indexing.
# Grouping messages improves conversational context in embeddings/chunks and
# drastically reduces the number of documents, embedding calls, and DB overhead.
SLACK_BATCH_SIZE = 100


def _build_batch_document_string(
    team_name: str,
    team_id: str,
    channel_name: str,
    channel_id: str,
    messages: list[dict],
) -> str:
    """
    Combine multiple Slack messages into a single document string.

    Each message is formatted with its timestamp and author, and all messages
    are concatenated into a conversation-style document. The chunker will
    later split this into overlapping windows of ~8-10 consecutive messages,
    preserving conversational context in each chunk's embedding.

    Args:
        team_name: Name of the Slack workspace
        team_id: ID of the Slack workspace
        channel_name: Name of the channel
        channel_id: ID of the channel
        messages: List of formatted message dicts with 'user_name', 'datetime', 'text'

    Returns:
        Formatted document string with metadata and conversation content
    """
    first_msg_time = messages[0].get("datetime", "Unknown")
    last_msg_time = messages[-1].get("datetime", "Unknown")

    metadata_lines = [
        f"WORKSPACE_NAME: {team_name}",
        f"WORKSPACE_ID: {team_id}",
        f"CHANNEL_NAME: {channel_name}",
        f"CHANNEL_ID: {channel_id}",
        f"MESSAGE_COUNT: {len(messages)}",
        f"FIRST_MESSAGE_TIME: {first_msg_time}",
        f"LAST_MESSAGE_TIME: {last_msg_time}",
    ]

    conversation_lines = []
    for msg in messages:
        author = msg.get("user_name", "Unknown User")
        timestamp = msg.get("datetime", "Unknown Time")
        content = msg.get("text", "")
        conversation_lines.append(f"[{timestamp}] {author}: {content}")

    metadata_sections = [
        ("METADATA", metadata_lines),
        (
            "CONTENT",
            [
                "FORMAT: markdown",
                "TEXT_START",
                "\n".join(conversation_lines),
                "TEXT_END",
            ],
        ),
    ]

    return build_document_metadata_markdown(metadata_sections)


async def index_slack_messages(
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
    Index Slack messages from all accessible channels.

    Messages are grouped into batches of SLACK_BATCH_SIZE per channel,
    so each document contains up to 100 consecutive messages with full
    conversational context. This reduces document count, embedding calls,
    and DB overhead by ~100x while improving search quality through
    context-aware chunk embeddings.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately)
    - Phase 2: Process each document: pending → processing → ready/failed

    Args:
        session: Database session
        connector_id: ID of the Slack connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.
            Called periodically with (indexed_count) to prevent task appearing stuck.

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

        # Extract workspace info from connector config
        team_id = connector.config.get("team_id", "")
        team_name = connector.config.get("team_name", "Unknown Workspace")

        # Note: Token handling is now done automatically by SlackHistory
        # with auto-refresh support. We just need to pass session and connector_id.

        # Initialize Slack client with auto-refresh support
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Slack client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        # Use the new pattern with session and connector_id for auto-refresh
        slack_client = SlackHistory(session=session, connector_id=connector_id)

        # Handle 'undefined' string from frontend (treat as None)
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

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
            channels = await slack_client.get_all_channels()
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
            # CRITICAL: Update timestamp even when no channels found so Electric SQL syncs
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return 0, None  # Return None (not error) when no channels found

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0  # Track messages that failed processing
        duplicate_content_count = 0
        total_messages_collected = 0
        skipped_channels = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(channels)} Slack channels",
            {"stage": "process_channels", "total_channels": len(channels)},
        )

        # =======================================================================
        # PHASE 1: Collect messages, group into batches, and create pending documents
        # Messages are grouped into batches of SLACK_BATCH_SIZE per channel.
        # Each batch becomes a single document with full conversational context.
        # All documents are visible in the UI immediately with pending status.
        # =======================================================================
        batches_to_process = []  # List of dicts with document and batch data
        new_documents_created = False

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
                messages, error = await slack_client.get_history_by_date_range(
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

                    formatted_msg = await slack_client.format_message(
                        msg, include_user_info=True
                    )
                    formatted_messages.append(formatted_msg)

                if not formatted_messages:
                    logger.info(
                        f"No valid messages found in channel {channel_name} after filtering."
                    )
                    documents_skipped += 1
                    continue  # Skip if no valid messages after filtering

                total_messages_collected += len(formatted_messages)

                # =======================================================
                # Group messages into batches of SLACK_BATCH_SIZE
                # Each batch becomes a single document with conversation context
                # =======================================================
                for batch_start in range(0, len(formatted_messages), SLACK_BATCH_SIZE):
                    batch = formatted_messages[
                        batch_start : batch_start + SLACK_BATCH_SIZE
                    ]

                    # Build combined document string from all messages in this batch
                    combined_document_string = _build_batch_document_string(
                        team_name=team_name,
                        team_id=team_id,
                        channel_name=channel_name,
                        channel_id=channel_id,
                        messages=batch,
                    )

                    # Generate unique identifier for this batch using
                    # channel_id + first message ts + last message ts
                    first_msg_ts = batch[0].get("timestamp", "")
                    last_msg_ts = batch[-1].get("timestamp", "")
                    unique_identifier = f"{channel_id}_{first_msg_ts}_{last_msg_ts}"
                    unique_identifier_hash = generate_unique_identifier_hash(
                        DocumentType.SLACK_CONNECTOR,
                        unique_identifier,
                        search_space_id,
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
                            # Ensure status is ready (might have been stuck in processing/pending)
                            if not DocumentStatus.is_state(
                                existing_document.status, DocumentStatus.READY
                            ):
                                existing_document.status = DocumentStatus.ready()
                            documents_skipped += 1
                            continue

                        # Queue existing document for update (will be set to processing in Phase 2)
                        batches_to_process.append(
                            {
                                "document": existing_document,
                                "is_new": False,
                                "combined_document_string": combined_document_string,
                                "content_hash": content_hash,
                                "team_name": team_name,
                                "team_id": team_id,
                                "channel_name": channel_name,
                                "channel_id": channel_id,
                                "first_message_ts": first_msg_ts,
                                "last_message_ts": last_msg_ts,
                                "first_message_time": batch[0].get(
                                    "datetime", "Unknown"
                                ),
                                "last_message_time": batch[-1].get(
                                    "datetime", "Unknown"
                                ),
                                "message_count": len(batch),
                                "start_date": start_date_str,
                                "end_date": end_date_str,
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
                        logger.info(
                            f"Slack batch ({len(batch)} msgs) in {team_name}#{channel_name} already indexed by another connector "
                            f"(existing document ID: {duplicate_by_content.id}, "
                            f"type: {duplicate_by_content.document_type}). Skipping."
                        )
                        duplicate_content_count += 1
                        documents_skipped += 1
                        continue

                    # Create new document with PENDING status (visible in UI immediately)
                    document = Document(
                        search_space_id=search_space_id,
                        title=f"{team_name}#{channel_name}",
                        document_type=DocumentType.SLACK_CONNECTOR,
                        document_metadata={
                            "team_name": team_name,
                            "team_id": team_id,
                            "channel_name": channel_name,
                            "channel_id": channel_id,
                            "first_message_ts": first_msg_ts,
                            "last_message_ts": last_msg_ts,
                            "message_count": len(batch),
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

                    batches_to_process.append(
                        {
                            "document": document,
                            "is_new": True,
                            "combined_document_string": combined_document_string,
                            "content_hash": content_hash,
                            "team_name": team_name,
                            "team_id": team_id,
                            "channel_name": channel_name,
                            "channel_id": channel_id,
                            "first_message_ts": first_msg_ts,
                            "last_message_ts": last_msg_ts,
                            "first_message_time": batch[0].get("datetime", "Unknown"),
                            "last_message_time": batch[-1].get("datetime", "Unknown"),
                            "message_count": len(batch),
                            "start_date": start_date_str,
                            "end_date": end_date_str,
                        }
                    )

                logger.info(
                    f"Phase 1: Collected {len(formatted_messages)} messages from channel {channel_name}, "
                    f"grouped into {(len(formatted_messages) + SLACK_BATCH_SIZE - 1) // SLACK_BATCH_SIZE} batch(es)"
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

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([b for b in batches_to_process if b['is_new']])} pending batch documents "
                f"({total_messages_collected} total messages across all channels)"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each batch document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(batches_to_process)} batch documents")

        for item in batches_to_process:
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

                # Heavy processing (embeddings, chunks)
                chunks = await create_document_chunks(item["combined_document_string"])
                doc_embedding = embed_text(item["combined_document_string"])

                # Update document to READY with actual content
                document.title = f"{item['team_name']}#{item['channel_name']}"
                document.content = item["combined_document_string"]
                document.content_hash = item["content_hash"]
                document.embedding = doc_embedding
                document.document_metadata = {
                    "team_name": item["team_name"],
                    "team_id": item["team_id"],
                    "channel_name": item["channel_name"],
                    "channel_id": item["channel_id"],
                    "first_message_ts": item["first_message_ts"],
                    "last_message_ts": item["last_message_ts"],
                    "first_message_time": item["first_message_time"],
                    "last_message_time": item["last_message_time"],
                    "message_count": item["message_count"],
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
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
                        f"Committing batch: {documents_indexed} batch documents processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing Slack batch document: {e!s}",
                    exc_info=True,
                )
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
            f"Final commit: Total {documents_indexed} batch documents processed "
            f"(from {total_messages_collected} messages)"
        )
        try:
            await session.commit()
            logger.info("Successfully committed all Slack document changes to database")
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same message was indexed by multiple connectors. "
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
        if skipped_channels:
            warning_parts.append(f"{len(skipped_channels)} channels skipped")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Slack indexing for connector {connector_id}",
            {
                "channels_processed": len(channels),
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
                "skipped_channels_count": len(skipped_channels),
                "total_messages_collected": total_messages_collected,
                "batch_size": SLACK_BATCH_SIZE,
                "team_id": team_id,
                "team_name": team_name,
            },
        )

        logger.info(
            f"Slack indexing completed for workspace {team_name}: "
            f"{documents_indexed} batch docs ready (from {total_messages_collected} messages), "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return documents_indexed, warning_message

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
