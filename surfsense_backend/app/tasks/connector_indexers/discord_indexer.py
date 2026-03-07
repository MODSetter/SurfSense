"""
Discord connector indexer.

Implements batch indexing: groups up to DISCORD_BATCH_SIZE messages per channel
into a single document for efficient indexing and better conversational context.

Uses 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.discord_connector import DiscordConnector
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
DISCORD_BATCH_SIZE = 100


def _build_batch_document_string(
    guild_name: str,
    guild_id: str,
    channel_name: str,
    channel_id: str,
    messages: list[dict],
) -> str:
    """
    Combine multiple Discord messages into a single document string.

    Each message is formatted with its timestamp and author, and all messages
    are concatenated into a conversation-style document. The chunker will
    later split this into overlapping windows of ~8-10 consecutive messages,
    preserving conversational context in each chunk's embedding.

    Args:
        guild_name: Name of the Discord guild
        guild_id: ID of the Discord guild
        channel_name: Name of the channel
        channel_id: ID of the channel
        messages: List of message dicts with 'author_name', 'created_at', 'content'

    Returns:
        Formatted document string with metadata and conversation content
    """
    first_msg_time = messages[0].get("created_at", "Unknown")
    last_msg_time = messages[-1].get("created_at", "Unknown")

    metadata_lines = [
        f"GUILD_NAME: {guild_name}",
        f"GUILD_ID: {guild_id}",
        f"CHANNEL_NAME: {channel_name}",
        f"CHANNEL_ID: {channel_id}",
        f"MESSAGE_COUNT: {len(messages)}",
        f"FIRST_MESSAGE_TIME: {first_msg_time}",
        f"LAST_MESSAGE_TIME: {last_msg_time}",
    ]

    conversation_lines = []
    for msg in messages:
        author = msg.get("author_name", "Unknown User")
        timestamp = msg.get("created_at", "Unknown Time")
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


async def index_discord_messages(
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
    Index Discord messages from the configured guild's channels.

    Messages are grouped into batches of DISCORD_BATCH_SIZE per channel,
    so each document contains up to 100 consecutive messages with full
    conversational context. This reduces document count, embedding calls,
    and DB overhead by ~100x while improving search quality through
    context-aware chunk embeddings.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately)
    - Phase 2: Process each document: pending → processing → ready/failed

    Args:
        session: Database session
        connector_id: ID of the Discord connector
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
        task_name="discord_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Discord messages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Normalize date parameters - handle 'undefined' strings from frontend
        if start_date and (
            start_date.lower() == "undefined" or start_date.strip() == ""
        ):
            start_date = None
        if end_date and (end_date.lower() == "undefined" or end_date.strip() == ""):
            end_date = None

        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Discord connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.DISCORD_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Discord connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Discord connector",
            )

        logger.info(f"Starting Discord indexing for connector {connector_id}")

        # =======================================================================
        # GUILD FILTERING: Only index the specific guild configured for this connector
        # =======================================================================
        # Extract guild_id from connector config (set during OAuth flow)
        configured_guild_id = connector.config.get("guild_id")
        configured_guild_name = connector.config.get("guild_name")

        # Legacy connector check - if no guild_id, we need to warn and handle gracefully
        is_legacy_connector = configured_guild_id is None

        if is_legacy_connector:
            logger.warning(
                f"Discord connector {connector_id} has no guild_id configured. "
                "This is a legacy connector. Please reconnect the Discord server to fix this. "
                "For now, indexing will be skipped to prevent indexing unwanted servers."
            )
            await task_logger.log_task_failure(
                log_entry,
                f"Legacy Discord connector {connector_id} missing guild_id",
                "No guild_id configured. Please reconnect this Discord server.",
                {"error_type": "MissingGuildId", "is_legacy": True},
            )
            return (
                0,
                "This Discord connector needs to be reconnected. Please disconnect and reconnect your Discord server to enable indexing.",
            )

        logger.info(
            f"Configured to index guild: {configured_guild_name} ({configured_guild_id})"
        )

        # Initialize Discord client with OAuth credentials support
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Discord client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        # Check if using OAuth (has bot_token in config) or legacy (has DISCORD_BOT_TOKEN)
        has_oauth = connector.config.get("bot_token") is not None
        has_legacy = connector.config.get("DISCORD_BOT_TOKEN") is not None

        if has_oauth:
            # Use OAuth credentials with auto-refresh
            discord_client = DiscordConnector(
                session=session, connector_id=connector_id
            )
        elif has_legacy:
            # Backward compatibility: use legacy token format
            discord_token = connector.config.get("DISCORD_BOT_TOKEN")

            # Decrypt token if it's encrypted (legacy tokens might be encrypted)
            token_encrypted = connector.config.get("_token_encrypted", False)
            if token_encrypted and config.SECRET_KEY and discord_token:
                try:
                    from app.utils.oauth_security import TokenEncryption

                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    discord_token = token_encryption.decrypt_token(discord_token)
                    logger.info(
                        f"Decrypted legacy Discord token for connector {connector_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to decrypt legacy Discord token for connector {connector_id}: {e!s}. "
                        "Trying to use token as-is (might be unencrypted)."
                    )
                    # Continue with token as-is - might be unencrypted legacy token

            discord_client = DiscordConnector(token=discord_token)
        else:
            await task_logger.log_task_failure(
                log_entry,
                f"Discord credentials not found in connector config for connector {connector_id}",
                "Missing Discord credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Discord credentials not found in connector config"

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now(UTC)

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                calculated_start_date = connector.last_indexed_at.replace(tzinfo=UTC)
                logger.info(
                    f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                )
            else:
                calculated_start_date = calculated_end_date - timedelta(days=365)
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided, convert to ISO format for Discord API
            if start_date is None:
                start_date_iso = calculated_start_date.isoformat()
            else:
                # Validate and convert YYYY-MM-DD to ISO format
                try:
                    start_date_iso = (
                        datetime.strptime(start_date, "%Y-%m-%d")
                        .replace(tzinfo=UTC)
                        .isoformat()
                    )
                except ValueError as e:
                    logger.warning(
                        f"Invalid start_date format '{start_date}', using calculated start date: {e!s}"
                    )
                    start_date_iso = calculated_start_date.isoformat()

            if end_date is None:
                end_date_iso = calculated_end_date.isoformat()
            else:
                # Validate and convert YYYY-MM-DD to ISO format
                try:
                    end_date_iso = (
                        datetime.strptime(end_date, "%Y-%m-%d")
                        .replace(tzinfo=UTC)
                        .isoformat()
                    )
                except ValueError as e:
                    logger.warning(
                        f"Invalid end_date format '{end_date}', using calculated end date: {e!s}"
                    )
                    end_date_iso = calculated_end_date.isoformat()
        else:
            # Convert provided dates to ISO format for Discord API
            try:
                start_date_iso = (
                    datetime.strptime(start_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )
            except ValueError as e:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Invalid start_date format: {start_date}",
                    f"Date parsing error: {e!s}",
                    {"error_type": "InvalidDateFormat", "start_date": start_date},
                )
                return (
                    0,
                    f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD format.",
                )

            try:
                end_date_iso = (
                    datetime.strptime(end_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )
            except ValueError as e:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Invalid end_date format: {end_date}",
                    f"Date parsing error: {e!s}",
                    {"error_type": "InvalidDateFormat", "end_date": end_date},
                )
                return (
                    0,
                    f"Invalid end_date format: {end_date}. Expected YYYY-MM-DD format.",
                )

        logger.info(
            f"Indexing Discord messages from {start_date_iso} to {end_date_iso}"
        )

        try:
            await task_logger.log_task_progress(
                log_entry,
                f"Starting Discord bot for connector {connector_id}",
                {"stage": "bot_initialization"},
            )

            logger.info("Starting Discord bot")
            discord_client._bot_task = asyncio.create_task(discord_client.start_bot())
            await discord_client._wait_until_ready()

            # We only process the configured guild, not all guilds
            logger.info(
                f"Processing configured guild only: {configured_guild_name} ({configured_guild_id})"
            )

        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to start Discord bot for connector {connector_id}",
                str(e),
                {"error_type": "BotStartError"},
            )
            logger.error(f"Failed to start Discord bot: {e!s}", exc_info=True)
            await discord_client.close_bot()
            return 0, f"Failed to start Discord bot: {e!s}"

        # Track results
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0
        duplicate_content_count = 0
        total_messages_collected = 0
        skipped_channels: list[str] = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        # Use the configured guild info
        guild_id = configured_guild_id
        guild_name = configured_guild_name or "Unknown Guild"

        await task_logger.log_task_progress(
            log_entry,
            f"Processing Discord guild: {guild_name}",
            {"stage": "process_guild", "guild_id": guild_id, "guild_name": guild_name},
        )

        # =======================================================================
        # PHASE 1: Collect messages, group into batches, and create pending documents
        # Messages are grouped into batches of DISCORD_BATCH_SIZE per channel.
        # Each batch becomes a single document with full conversational context.
        # All documents are visible in the UI immediately with pending status.
        # =======================================================================
        batches_to_process = []  # List of dicts with document and batch data
        new_documents_created = False

        try:
            logger.info(f"Processing guild: {guild_name} ({guild_id})")

            try:
                channels = await discord_client.get_text_channels(guild_id)
                if not channels:
                    logger.info(f"No channels found in guild {guild_name}. Skipping.")
                    skipped_channels.append(f"{guild_name} (no channels)")
                else:
                    for channel in channels:
                        channel_id = channel["id"]
                        channel_name = channel["name"]

                        try:
                            messages = await discord_client.get_channel_history(
                                channel_id=channel_id,
                                start_date=start_date_iso,
                                end_date=end_date_iso,
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to get messages for channel {channel_name}: {e!s}"
                            )
                            skipped_channels.append(
                                f"{guild_name}#{channel_name} (fetch error)"
                            )
                            continue

                        if not messages:
                            logger.info(
                                f"No messages found in channel {channel_name} for the specified date range."
                            )
                            continue

                        # Filter/format messages
                        formatted_messages: list[dict] = []
                        for msg in messages:
                            # Optionally skip system messages
                            if msg.get("type") in ["system"]:
                                continue
                            formatted_messages.append(msg)

                        if not formatted_messages:
                            logger.info(
                                f"No valid messages found in channel {channel_name} after filtering."
                            )
                            continue

                        total_messages_collected += len(formatted_messages)

                        # =======================================================
                        # Group messages into batches of DISCORD_BATCH_SIZE
                        # Each batch becomes a single document with conversation context
                        # =======================================================
                        for batch_start in range(
                            0, len(formatted_messages), DISCORD_BATCH_SIZE
                        ):
                            batch = formatted_messages[
                                batch_start : batch_start + DISCORD_BATCH_SIZE
                            ]

                            # Build combined document string from all messages in this batch
                            combined_document_string = _build_batch_document_string(
                                guild_name=guild_name,
                                guild_id=guild_id,
                                channel_name=channel_name,
                                channel_id=channel_id,
                                messages=batch,
                            )

                            # Generate unique identifier for this batch using
                            # channel_id + first message ID + last message ID
                            first_msg_id = batch[0].get("id", "")
                            last_msg_id = batch[-1].get("id", "")
                            unique_identifier = (
                                f"{channel_id}_{first_msg_id}_{last_msg_id}"
                            )
                            unique_identifier_hash = generate_unique_identifier_hash(
                                DocumentType.DISCORD_CONNECTOR,
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
                                    # Ensure status is ready (might have been stuck in processing/pending)
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
                                        "guild_name": guild_name,
                                        "guild_id": guild_id,
                                        "channel_name": channel_name,
                                        "channel_id": channel_id,
                                        "first_message_id": first_msg_id,
                                        "last_message_id": last_msg_id,
                                        "first_message_time": batch[0].get(
                                            "created_at", "Unknown"
                                        ),
                                        "last_message_time": batch[-1].get(
                                            "created_at", "Unknown"
                                        ),
                                        "message_count": len(batch),
                                    }
                                )
                                continue

                            # Document doesn't exist by unique_identifier_hash
                            # Check if a document with the same content_hash exists (from another connector)
                            with session.no_autoflush:
                                duplicate_by_content = (
                                    await check_duplicate_document_by_hash(
                                        session, content_hash
                                    )
                                )

                            if duplicate_by_content:
                                logger.info(
                                    f"Discord batch ({len(batch)} msgs) in {guild_name}#{channel_name} already indexed by another connector "
                                    f"(existing document ID: {duplicate_by_content.id}, "
                                    f"type: {duplicate_by_content.document_type}). Skipping."
                                )
                                duplicate_content_count += 1
                                documents_skipped += 1
                                continue

                            # Create new document with PENDING status (visible in UI immediately)
                            document = Document(
                                search_space_id=search_space_id,
                                title=f"{guild_name}#{channel_name}",
                                document_type=DocumentType.DISCORD_CONNECTOR,
                                document_metadata={
                                    "guild_name": guild_name,
                                    "guild_id": guild_id,
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
                                    "guild_name": guild_name,
                                    "guild_id": guild_id,
                                    "channel_name": channel_name,
                                    "channel_id": channel_id,
                                    "first_message_id": first_msg_id,
                                    "last_message_id": last_msg_id,
                                    "first_message_time": batch[0].get(
                                        "created_at", "Unknown"
                                    ),
                                    "last_message_time": batch[-1].get(
                                        "created_at", "Unknown"
                                    ),
                                    "message_count": len(batch),
                                }
                            )

                        logger.info(
                            f"Phase 1: Collected {len(formatted_messages)} messages from channel {channel_name}, "
                            f"grouped into {(len(formatted_messages) + DISCORD_BATCH_SIZE - 1) // DISCORD_BATCH_SIZE} batch(es)"
                        )

            except Exception as e:
                logger.error(
                    f"Error processing guild {guild_name}: {e!s}", exc_info=True
                )
                skipped_channels.append(f"{guild_name} (processing error)")

        finally:
            await discord_client.close_bot()

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
                document.title = f"{item['guild_name']}#{item['channel_name']}"
                document.content = item["combined_document_string"]
                document.content_hash = item["content_hash"]
                document.embedding = doc_embedding
                document.document_metadata = {
                    "guild_name": item["guild_name"],
                    "guild_id": item["guild_id"],
                    "channel_name": item["channel_name"],
                    "channel_id": item["channel_id"],
                    "first_message_id": item["first_message_id"],
                    "last_message_id": item["last_message_id"],
                    "first_message_time": item["first_message_time"],
                    "last_message_time": item["last_message_time"],
                    "message_count": item["message_count"],
                    "indexed_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
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
                    f"Error processing Discord batch document: {e!s}", exc_info=True
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
            logger.info(
                "Successfully committed all Discord document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
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
            f"Successfully completed Discord indexing for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
                "skipped_channels_count": len(skipped_channels),
                "total_messages_collected": total_messages_collected,
                "batch_size": DISCORD_BATCH_SIZE,
                "guild_id": guild_id,
                "guild_name": guild_name,
            },
        )

        logger.info(
            f"Discord indexing completed for guild {guild_name}: "
            f"{documents_indexed} batch docs ready (from {total_messages_collected} messages), "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return documents_indexed, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Discord indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Discord messages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Discord messages: {e!s}", exc_info=True)
        return 0, f"Failed to index Discord messages: {e!s}"
