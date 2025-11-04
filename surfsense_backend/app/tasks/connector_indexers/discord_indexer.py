"""
Discord connector indexer.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.discord_connector import DiscordConnector
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
    build_document_metadata_string,
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_discord_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Discord messages from all accessible channels.

    Args:
        session: Database session
        connector_id: ID of the Discord connector
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

        # Get the Discord token from the connector config
        discord_token = connector.config.get("DISCORD_BOT_TOKEN")
        if not discord_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Discord token not found in connector config for connector {connector_id}",
                "Missing Discord token",
                {"error_type": "MissingToken"},
            )
            return 0, "Discord token not found in connector config"

        logger.info(f"Starting Discord indexing for connector {connector_id}")

        # Initialize Discord client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Discord client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        discord_client = DiscordConnector(token=discord_token)

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
                # Convert YYYY-MM-DD to ISO format
                start_date_iso = (
                    datetime.strptime(start_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )

            if end_date is None:
                end_date_iso = calculated_end_date.isoformat()
            else:
                # Convert YYYY-MM-DD to ISO format
                end_date_iso = (
                    datetime.strptime(end_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )
        else:
            # Convert provided dates to ISO format for Discord API
            start_date_iso = (
                datetime.strptime(start_date, "%Y-%m-%d")
                .replace(tzinfo=UTC)
                .isoformat()
            )
            end_date_iso = (
                datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).isoformat()
            )

        logger.info(
            f"Indexing Discord messages from {start_date_iso} to {end_date_iso}"
        )

        try:
            await task_logger.log_task_progress(
                log_entry,
                f"Starting Discord bot and fetching guilds for connector {connector_id}",
                {"stage": "fetch_guilds"},
            )

            logger.info("Starting Discord bot to fetch guilds")
            discord_client._bot_task = asyncio.create_task(discord_client.start_bot())
            await discord_client._wait_until_ready()

            logger.info("Fetching Discord guilds")
            guilds = await discord_client.get_guilds()
            logger.info(f"Found {len(guilds)} guilds")
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Discord guilds for connector {connector_id}",
                str(e),
                {"error_type": "GuildFetchError"},
            )
            logger.error(f"Failed to get Discord guilds: {e!s}", exc_info=True)
            await discord_client.close_bot()
            return 0, f"Failed to get Discord guilds: {e!s}"

        if not guilds:
            await task_logger.log_task_success(
                log_entry,
                f"No Discord guilds found for connector {connector_id}",
                {"guilds_found": 0},
            )
            logger.info("No Discord guilds found to index")
            await discord_client.close_bot()
            return 0, "No Discord guilds found"

        # Track results
        documents_indexed = 0
        documents_skipped = 0
        skipped_channels: list[str] = []

        # Process each guild and channel
        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(guilds)} Discord guilds",
            {"stage": "process_guilds", "total_guilds": len(guilds)},
        )

        try:
            for guild in guilds:
                guild_id = guild["id"]
                guild_name = guild["name"]
                logger.info(f"Processing guild: {guild_name} ({guild_id})")

                try:
                    channels = await discord_client.get_text_channels(guild_id)
                    if not channels:
                        logger.info(
                            f"No channels found in guild {guild_name}. Skipping."
                        )
                        skipped_channels.append(f"{guild_name} (no channels)")
                        documents_skipped += 1
                        continue

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
                            documents_skipped += 1
                            continue

                        if not messages:
                            logger.info(
                                f"No messages found in channel {channel_name} for the specified date range."
                            )
                            documents_skipped += 1
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
                            documents_skipped += 1
                            continue

                        # Convert messages to markdown format
                        channel_content = (
                            f"# Discord Channel: {guild_name} / {channel_name}\n\n"
                        )
                        for msg in formatted_messages:
                            user_name = msg.get("author_name", "Unknown User")
                            timestamp = msg.get("created_at", "Unknown Time")
                            text = msg.get("content", "")
                            channel_content += (
                                f"## {user_name} ({timestamp})\n\n{text}\n\n---\n\n"
                            )

                        # Metadata sections
                        metadata_sections = [
                            (
                                "METADATA",
                                [
                                    f"GUILD_NAME: {guild_name}",
                                    f"GUILD_ID: {guild_id}",
                                    f"CHANNEL_NAME: {channel_name}",
                                    f"CHANNEL_ID: {channel_id}",
                                    f"MESSAGE_COUNT: {len(formatted_messages)}",
                                ],
                            ),
                            (
                                "CONTENT",
                                [
                                    "FORMAT: markdown",
                                    "TEXT_START",
                                    channel_content,
                                    "TEXT_END",
                                ],
                            ),
                        ]

                        combined_document_string = build_document_metadata_string(
                            metadata_sections
                        )

                        # Generate unique identifier hash for this Discord channel
                        unique_identifier_hash = generate_unique_identifier_hash(
                            DocumentType.DISCORD_CONNECTOR, channel_id, search_space_id
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
                                    f"Document for Discord channel {guild_name}#{channel_name} unchanged. Skipping."
                                )
                                documents_skipped += 1
                                continue
                            else:
                                # Content has changed - update the existing document
                                logger.info(
                                    f"Content changed for Discord channel {guild_name}#{channel_name}. Updating document."
                                )

                                # Get user's long context LLM
                                user_llm = await get_user_long_context_llm(
                                    session, user_id, search_space_id
                                )
                                if not user_llm:
                                    logger.error(
                                        f"No long context LLM configured for user {user_id}"
                                    )
                                    skipped_channels.append(
                                        f"{guild_name}#{channel_name} (no LLM configured)"
                                    )
                                    documents_skipped += 1
                                    continue

                                # Generate summary with metadata
                                document_metadata = {
                                    "guild_name": guild_name,
                                    "channel_name": channel_name,
                                    "message_count": len(formatted_messages),
                                    "document_type": "Discord Channel Messages",
                                    "connector_type": "Discord",
                                }
                                (
                                    summary_content,
                                    summary_embedding,
                                ) = await generate_document_summary(
                                    combined_document_string,
                                    user_llm,
                                    document_metadata,
                                )

                                # Chunks from channel content
                                chunks = await create_document_chunks(channel_content)

                                # Update existing document
                                existing_document.title = (
                                    f"Discord - {guild_name}#{channel_name}"
                                )
                                existing_document.content = summary_content
                                existing_document.content_hash = content_hash
                                existing_document.embedding = summary_embedding
                                existing_document.document_metadata = {
                                    "guild_name": guild_name,
                                    "guild_id": guild_id,
                                    "channel_name": channel_name,
                                    "channel_id": channel_id,
                                    "message_count": len(formatted_messages),
                                    "start_date": start_date_iso,
                                    "end_date": end_date_iso,
                                    "indexed_at": datetime.now(UTC).strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                                existing_document.chunks = chunks

                                documents_indexed += 1
                                logger.info(
                                    f"Successfully updated Discord channel {guild_name}#{channel_name}"
                                )
                                continue

                        # Document doesn't exist - create new one
                        # Get user's long context LLM
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )
                        if not user_llm:
                            logger.error(
                                f"No long context LLM configured for user {user_id}"
                            )
                            skipped_channels.append(
                                f"{guild_name}#{channel_name} (no LLM configured)"
                            )
                            documents_skipped += 1
                            continue

                        # Generate summary with metadata
                        document_metadata = {
                            "guild_name": guild_name,
                            "channel_name": channel_name,
                            "message_count": len(formatted_messages),
                            "document_type": "Discord Channel Messages",
                            "connector_type": "Discord",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            combined_document_string, user_llm, document_metadata
                        )

                        # Chunks from channel content
                        chunks = await create_document_chunks(channel_content)

                        # Create and store new document
                        document = Document(
                            search_space_id=search_space_id,
                            title=f"Discord - {guild_name}#{channel_name}",
                            document_type=DocumentType.DISCORD_CONNECTOR,
                            document_metadata={
                                "guild_name": guild_name,
                                "guild_id": guild_id,
                                "channel_name": channel_name,
                                "channel_id": channel_id,
                                "message_count": len(formatted_messages),
                                "start_date": start_date_iso,
                                "end_date": end_date_iso,
                                "indexed_at": datetime.now(UTC).strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            },
                            content=summary_content,
                            content_hash=content_hash,
                            unique_identifier_hash=unique_identifier_hash,
                            embedding=summary_embedding,
                            chunks=chunks,
                        )

                        session.add(document)
                        documents_indexed += 1
                        logger.info(
                            f"Successfully indexed new channel {guild_name}#{channel_name} with {len(formatted_messages)} messages"
                        )

                        # Batch commit every 10 documents
                        if documents_indexed % 10 == 0:
                            logger.info(
                                f"Committing batch: {documents_indexed} Discord channels processed so far"
                            )
                            await session.commit()

                except Exception as e:
                    logger.error(
                        f"Error processing guild {guild_name}: {e!s}", exc_info=True
                    )
                    skipped_channels.append(f"{guild_name} (processing error)")
                    documents_skipped += 1
                    continue
        finally:
            await discord_client.close_bot()

        # Update last_indexed_at only if we indexed at least one
        if documents_indexed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} Discord channels processed"
        )
        await session.commit()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = (
                f"Processed {documents_indexed} channels. Skipped {len(skipped_channels)} channels: "
                + ", ".join(skipped_channels)
            )
        else:
            result_message = f"Processed {documents_indexed} channels."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Discord indexing for connector {connector_id}",
            {
                "channels_processed": documents_indexed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_channels_count": len(skipped_channels),
                "guilds_processed": len(guilds),
                "result_message": result_message,
            },
        )

        logger.info(
            f"Discord indexing completed: {documents_indexed} new channels, {documents_skipped} skipped"
        )
        return documents_indexed, result_message

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
