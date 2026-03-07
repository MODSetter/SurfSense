"""
Microsoft Teams connector indexer.

Implements batch indexing: groups up to TEAMS_BATCH_SIZE messages per channel
into a single document for efficient indexing and better conversational context.

Uses 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.teams_history import TeamsHistory
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
TEAMS_BATCH_SIZE = 100


def _build_batch_document_string(
    team_name: str,
    team_id: str,
    channel_name: str,
    channel_id: str,
    messages: list[dict],
) -> str:
    """
    Combine multiple Teams messages into a single document string.

    Each message is formatted with its timestamp and author, and all messages
    are concatenated into a conversation-style document. The chunker will
    later split this into overlapping windows of ~8-10 consecutive messages,
    preserving conversational context in each chunk's embedding.

    Args:
        team_name: Name of the Microsoft Team
        team_id: ID of the Microsoft Team
        channel_name: Name of the channel
        channel_id: ID of the channel
        messages: List of formatted message dicts with 'user_name', 'created_datetime', 'content'

    Returns:
        Formatted document string with metadata and conversation content
    """
    first_msg_time = messages[0].get("created_datetime", "Unknown")
    last_msg_time = messages[-1].get("created_datetime", "Unknown")

    metadata_lines = [
        f"TEAM_NAME: {team_name}",
        f"TEAM_ID: {team_id}",
        f"CHANNEL_NAME: {channel_name}",
        f"CHANNEL_ID: {channel_id}",
        f"MESSAGE_COUNT: {len(messages)}",
        f"FIRST_MESSAGE_TIME: {first_msg_time}",
        f"LAST_MESSAGE_TIME: {last_msg_time}",
    ]

    conversation_lines = []
    for msg in messages:
        author = msg.get("user_name", "Unknown User")
        timestamp = msg.get("created_datetime", "Unknown Time")
        content = msg.get("content", "")
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


async def index_teams_messages(
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
    Index Microsoft Teams messages from all accessible teams and channels.

    Messages are grouped into batches of TEAMS_BATCH_SIZE per channel,
    so each document contains up to 100 consecutive messages with full
    conversational context. This reduces document count, embedding calls,
    and DB overhead by ~100x while improving search quality through
    context-aware chunk embeddings.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately)
    - Phase 2: Process each document: pending → processing → ready/failed

    Args:
        session: Database session
        connector_id: ID of the Teams connector
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
        task_name="teams_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Microsoft Teams messages indexing for connector {connector_id}",
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
            f"Retrieving Teams connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.TEAMS_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Teams connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Teams connector",
            )

        # Initialize Teams client with auto-refresh support
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Teams client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        teams_client = TeamsHistory(session=session, connector_id=connector_id)

        # Handle 'undefined' string from frontend (treat as None)
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range
        await task_logger.log_task_progress(
            log_entry,
            "Calculating date range for Teams indexing",
            {
                "stage": "date_calculation",
                "provided_start_date": start_date,
                "provided_end_date": end_date,
            },
        )

        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        logger.info(
            "Indexing Teams messages from %s to %s", start_date_str, end_date_str
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Teams from {start_date_str} to {end_date_str}",
            {
                "stage": "fetch_teams",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get all teams
        try:
            teams = await teams_client.get_all_teams()
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Teams for connector {connector_id}",
                str(e),
                {"error_type": "TeamsFetchError"},
            )
            return 0, f"Failed to get Teams: {e!s}"

        if not teams:
            await task_logger.log_task_success(
                log_entry,
                f"No Teams found for connector {connector_id}",
                {"teams_found": 0},
            )
            # CRITICAL: Update timestamp even when no teams found so Electric SQL syncs
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            return 0, None  # Return None (not error) when no items found

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0
        duplicate_content_count = 0
        total_messages_collected = 0
        skipped_channels = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(teams)} Teams",
            {"stage": "process_teams", "total_teams": len(teams)},
        )

        # Convert date strings to datetime objects for filtering
        start_datetime = None
        end_datetime = None
        if start_date_str:
            start_datetime = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
                tzinfo=UTC
            )
        if end_date_str:
            end_datetime = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=UTC
            )

        # =======================================================================
        # PHASE 1: Collect messages, group into batches, and create pending documents
        # Messages are grouped into batches of TEAMS_BATCH_SIZE per channel.
        # Each batch becomes a single document with full conversational context.
        # All documents are visible in the UI immediately with pending status.
        # =======================================================================
        batches_to_process = []  # List of dicts with document and batch data
        new_documents_created = False

        for team in teams:
            team_id = team.get("id")
            team_name = team.get("displayName", "Unknown Team")

            try:
                # Get channels for this team
                channels = await teams_client.get_channels_for_team(team_id)

                if not channels:
                    logger.info("No channels found in team %s", team_name)
                    continue

                # Process each channel in the team
                for channel in channels:
                    channel_id = channel.get("id")
                    channel_name = channel.get("displayName", "Unknown Channel")

                    try:
                        # Get messages for this channel
                        messages = await teams_client.get_messages_from_channel(
                            team_id,
                            channel_id,
                            start_datetime,
                            end_datetime,
                            include_replies=True,
                        )

                        if not messages:
                            logger.info(
                                "No messages found in channel %s of team %s for the specified date range.",
                                channel_name,
                                team_name,
                            )
                            continue

                        # Format messages for batching
                        formatted_messages = []
                        for msg in messages:
                            # Skip deleted messages or empty content
                            if msg.get("deletedDateTime"):
                                continue

                            from_user = msg.get("from", {})
                            user_name = from_user.get("user", {}).get(
                                "displayName", "Unknown User"
                            )

                            body = msg.get("body", {})
                            msg_text = body.get("content", "")

                            # Skip empty messages
                            if not msg_text or msg_text.strip() == "":
                                continue

                            formatted_messages.append(
                                {
                                    "message_id": msg.get("id", ""),
                                    "created_datetime": msg.get("createdDateTime", ""),
                                    "user_name": user_name,
                                    "content": msg_text,
                                }
                            )

                        if not formatted_messages:
                            logger.info(
                                "No valid messages found in channel %s of team %s after filtering.",
                                channel_name,
                                team_name,
                            )
                            documents_skipped += 1
                            continue

                        total_messages_collected += len(formatted_messages)

                        # =======================================================
                        # Group messages into batches of TEAMS_BATCH_SIZE
                        # Each batch becomes a single document with conversation context
                        # =======================================================
                        for batch_start in range(
                            0, len(formatted_messages), TEAMS_BATCH_SIZE
                        ):
                            batch = formatted_messages[
                                batch_start : batch_start + TEAMS_BATCH_SIZE
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
                            # team_id + channel_id + first message id + last message id
                            first_msg_id = batch[0].get("message_id", "")
                            last_msg_id = batch[-1].get("message_id", "")
                            unique_identifier = (
                                f"{team_id}_{channel_id}_{first_msg_id}_{last_msg_id}"
                            )
                            unique_identifier_hash = generate_unique_identifier_hash(
                                DocumentType.TEAMS_CONNECTOR,
                                unique_identifier,
                                search_space_id,
                            )

                            # Generate content hash
                            content_hash = generate_content_hash(
                                combined_document_string, search_space_id
                            )

                            # Check if document with this unique identifier already exists
                            existing_document = (
                                await check_document_by_unique_identifier(
                                    session, unique_identifier_hash
                                )
                            )

                            if existing_document:
                                # Document exists - check if content has changed
                                if existing_document.content_hash == content_hash:
                                    if not DocumentStatus.is_state(
                                        existing_document.status, DocumentStatus.READY
                                    ):
                                        existing_document.status = (
                                            DocumentStatus.ready()
                                        )
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
                                        "first_message_id": first_msg_id,
                                        "last_message_id": last_msg_id,
                                        "first_message_time": batch[0].get(
                                            "created_datetime", "Unknown"
                                        ),
                                        "last_message_time": batch[-1].get(
                                            "created_datetime", "Unknown"
                                        ),
                                        "message_count": len(batch),
                                        "start_date": start_date_str,
                                        "end_date": end_date_str,
                                    }
                                )
                                continue

                            # Check if a document with the same content_hash exists (from another connector)
                            with session.no_autoflush:
                                duplicate_by_content = (
                                    await check_duplicate_document_by_hash(
                                        session, content_hash
                                    )
                                )

                            if duplicate_by_content:
                                logger.info(
                                    "Teams batch (%s msgs) in %s/%s already indexed by another connector "
                                    "(existing document ID: %s, type: %s). Skipping.",
                                    len(batch),
                                    team_name,
                                    channel_name,
                                    duplicate_by_content.id,
                                    duplicate_by_content.document_type,
                                )
                                duplicate_content_count += 1
                                documents_skipped += 1
                                continue

                            # Create new document with PENDING status (visible in UI immediately)
                            document = Document(
                                search_space_id=search_space_id,
                                title=f"{team_name} - {channel_name}",
                                document_type=DocumentType.TEAMS_CONNECTOR,
                                document_metadata={
                                    "team_name": team_name,
                                    "team_id": team_id,
                                    "channel_name": channel_name,
                                    "channel_id": channel_id,
                                    "first_message_id": first_msg_id,
                                    "last_message_id": last_msg_id,
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
                                    "first_message_id": first_msg_id,
                                    "last_message_id": last_msg_id,
                                    "first_message_time": batch[0].get(
                                        "created_datetime", "Unknown"
                                    ),
                                    "last_message_time": batch[-1].get(
                                        "created_datetime", "Unknown"
                                    ),
                                    "message_count": len(batch),
                                    "start_date": start_date_str,
                                    "end_date": end_date_str,
                                }
                            )

                        logger.info(
                            "Phase 1: Collected %s messages from %s/%s, "
                            "grouped into %s batch(es)",
                            len(formatted_messages),
                            team_name,
                            channel_name,
                            (len(formatted_messages) + TEAMS_BATCH_SIZE - 1)
                            // TEAMS_BATCH_SIZE,
                        )

                    except Exception as e:
                        logger.error(
                            "Error processing channel %s in team %s: %s",
                            channel_name,
                            team_name,
                            str(e),
                        )
                        skipped_channels.append(
                            f"{team_name}/{channel_name} (processing error)"
                        )
                        continue

            except Exception as e:
                logger.error("Error processing team %s: %s", team_name, str(e))
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                "Phase 1: Committing %s pending batch documents "
                "(%s total messages across all channels)",
                len([b for b in batches_to_process if b["is_new"]]),
                total_messages_collected,
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each batch document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info("Phase 2: Processing %s batch documents", len(batches_to_process))

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
                document.title = f"{item['team_name']} - {item['channel_name']}"
                document.content = item["combined_document_string"]
                document.content_hash = item["content_hash"]
                document.embedding = doc_embedding
                document.document_metadata = {
                    "team_name": item["team_name"],
                    "team_id": item["team_id"],
                    "channel_name": item["channel_name"],
                    "channel_id": item["channel_id"],
                    "first_message_id": item["first_message_id"],
                    "last_message_id": item["last_message_id"],
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
                        "Committing batch: %s Teams batch documents processed so far",
                        documents_indexed,
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    "Error processing Teams batch document: %s",
                    str(e),
                    exc_info=True,
                )
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(e))
                    document.updated_at = get_current_timestamp()
                except Exception as status_error:
                    logger.error(
                        "Failed to update document status to failed: %s",
                        str(status_error),
                    )
                documents_failed += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            "Final commit: Total %s Teams batch documents processed (from %s messages)",
            documents_indexed,
            total_messages_collected,
        )
        try:
            await session.commit()
            logger.info("Successfully committed all Teams document changes to database")
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    "Duplicate content_hash detected during final commit. "
                    "Rolling back and continuing. Error: %s",
                    str(e),
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
            f"Successfully completed Teams indexing for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
                "skipped_channels_count": len(skipped_channels),
                "total_messages_collected": total_messages_collected,
                "batch_size": TEAMS_BATCH_SIZE,
            },
        )

        logger.info(
            "Teams indexing completed: %s batch docs ready (from %s messages), "
            "%s skipped, %s failed (%s duplicate content)",
            documents_indexed,
            total_messages_collected,
            documents_skipped,
            documents_failed,
            duplicate_content_count,
        )
        return documents_indexed, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Teams indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error("Database error: %s", str(db_error))
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Teams messages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error("Failed to index Teams messages: %s", str(e))
        return 0, f"Failed to index Teams messages: {e!s}"
