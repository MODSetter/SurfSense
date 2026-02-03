"""
Microsoft Teams connector indexer.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.teams_history import TeamsHistory
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
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    update_connector_last_indexed,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds - update notification every 30 seconds
HEARTBEAT_INTERVAL_SECONDS = 30


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
            return 0, "No Teams found"

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(teams)} Teams",
            {"stage": "process_teams", "total_teams": len(teams)},
        )

        # Convert date strings to datetime objects for filtering
        from datetime import datetime

        start_datetime = None
        end_datetime = None
        if start_date_str:
            # Parse as naive datetime and make it timezone-aware (UTC)
            start_datetime = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
                tzinfo=UTC
            )
        if end_date_str:
            # Parse as naive datetime, set to end of day, and make it timezone-aware (UTC)
            end_datetime = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=UTC
            )

        # Process each team
        for team in teams:
            # Check if it's time for a heartbeat update
            if (
                on_heartbeat_callback
                and (time.time() - last_heartbeat_time) >= HEARTBEAT_INTERVAL_SECONDS
            ):
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = time.time()

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
                            documents_skipped += 1
                            continue

                        # Process each message
                        for msg in messages:
                            # Skip deleted messages or empty content
                            if msg.get("deletedDateTime"):
                                continue

                            # Extract message details
                            message_id = msg.get("id", "")
                            created_datetime = msg.get("createdDateTime", "")
                            from_user = msg.get("from", {})
                            user_name = from_user.get("user", {}).get(
                                "displayName", "Unknown User"
                            )
                            user_email = from_user.get("user", {}).get(
                                "userPrincipalName", "Unknown Email"
                            )

                            # Extract message content
                            body = msg.get("body", {})
                            content_type = body.get("contentType", "text")
                            msg_text = body.get("content", "")

                            # Skip empty messages
                            if not msg_text or msg_text.strip() == "":
                                continue

                            # Format document metadata
                            metadata_sections = [
                                (
                                    "METADATA",
                                    [
                                        f"TEAM_NAME: {team_name}",
                                        f"TEAM_ID: {team_id}",
                                        f"CHANNEL_NAME: {channel_name}",
                                        f"CHANNEL_ID: {channel_id}",
                                        f"MESSAGE_TIMESTAMP: {created_datetime}",
                                        f"MESSAGE_USER_NAME: {user_name}",
                                        f"MESSAGE_USER_EMAIL: {user_email}",
                                        f"CONTENT_TYPE: {content_type}",
                                    ],
                                ),
                                (
                                    "CONTENT",
                                    [
                                        f"FORMAT: {content_type}",
                                        "TEXT_START",
                                        msg_text,
                                        "TEXT_END",
                                    ],
                                ),
                            ]

                            # Build the document string
                            combined_document_string = build_document_metadata_markdown(
                                metadata_sections
                            )

                            # Generate unique identifier hash for this Teams message
                            unique_identifier = f"{team_id}_{channel_id}_{message_id}"
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
                                    logger.info(
                                        "Document for Teams message %s in channel %s unchanged. Skipping.",
                                        message_id,
                                        channel_name,
                                    )
                                    documents_skipped += 1
                                    continue
                                else:
                                    # Content has changed - update the existing document
                                    logger.info(
                                        "Content changed for Teams message %s in channel %s. Updating document.",
                                        message_id,
                                        channel_name,
                                    )

                                    # Update chunks and embedding
                                    chunks = await create_document_chunks(
                                        combined_document_string
                                    )
                                    doc_embedding = (
                                        config.embedding_model_instance.embed(
                                            combined_document_string
                                        )
                                    )

                                    # Update existing document
                                    existing_document.content = combined_document_string
                                    existing_document.content_hash = content_hash
                                    existing_document.embedding = doc_embedding
                                    existing_document.document_metadata = {
                                        "team_name": team_name,
                                        "team_id": team_id,
                                        "channel_name": channel_name,
                                        "channel_id": channel_id,
                                        "start_date": start_date_str,
                                        "end_date": end_date_str,
                                        "message_count": len(messages),
                                        "indexed_at": datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }

                                    # Delete old chunks and add new ones
                                    existing_document.chunks = chunks
                                    existing_document.updated_at = (
                                        get_current_timestamp()
                                    )

                                    documents_indexed += 1
                                    logger.info(
                                        "Successfully updated Teams message %s",
                                        message_id,
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
                                    "Teams message %s in channel %s already indexed by another connector "
                                    "(existing document ID: %s, type: %s). Skipping.",
                                    message_id,
                                    channel_name,
                                    duplicate_by_content.id,
                                    duplicate_by_content.document_type,
                                )
                                documents_skipped += 1
                                continue

                            # Document doesn't exist - create new one
                            # Process chunks
                            chunks = await create_document_chunks(
                                combined_document_string
                            )
                            doc_embedding = config.embedding_model_instance.embed(
                                combined_document_string
                            )

                            # Create and store new document
                            document = Document(
                                search_space_id=search_space_id,
                                title=f"Teams - {team_name} - {channel_name}",
                                document_type=DocumentType.TEAMS_CONNECTOR,
                                document_metadata={
                                    "team_name": team_name,
                                    "team_id": team_id,
                                    "channel_name": channel_name,
                                    "channel_id": channel_id,
                                    "start_date": start_date_str,
                                    "end_date": end_date_str,
                                    "message_count": len(messages),
                                    "indexed_at": datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                },
                                content=combined_document_string,
                                embedding=doc_embedding,
                                chunks=chunks,
                                content_hash=content_hash,
                                unique_identifier_hash=unique_identifier_hash,
                                updated_at=get_current_timestamp(),
                                created_by_id=user_id,
                                connector_id=connector_id,
                            )

                            session.add(document)
                            documents_indexed += 1

                            # Batch commit every 10 documents
                            if documents_indexed % 10 == 0:
                                logger.info(
                                    "Committing batch: %s Teams messages processed so far",
                                    documents_indexed,
                                )
                                await session.commit()

                        logger.info(
                            "Successfully indexed channel %s in team %s with %s messages",
                            channel_name,
                            team_name,
                            len(messages),
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
                        documents_skipped += 1
                        continue

            except Exception as e:
                logger.error("Error processing team %s: %s", team_name, str(e))
                continue

        # Update the last_indexed_at timestamp for the connector only if requested
        # and if we successfully indexed at least one document
        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            "Final commit: Total %s Teams messages processed", documents_indexed
        )
        await session.commit()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {total_processed} messages. Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {total_processed} messages."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Teams indexing for connector {connector_id}",
            {
                "messages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_channels_count": len(skipped_channels),
                "result_message": result_message,
            },
        )

        logger.info(
            "Teams indexing completed: %s new messages, %s skipped",
            documents_indexed,
            documents_skipped,
        )
        return (
            total_processed,
            None,
        )  # Return None on success (result_message is for logging only)

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
