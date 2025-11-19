"""
Home Assistant connector indexer.
"""

from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.home_assistant_connector import HomeAssistantConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_home_assistant_data(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Home Assistant data including automations, scripts, scenes, and logbook events.

    Args:
        session: Database session
        connector_id: ID of the Home Assistant connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing logbook events (YYYY-MM-DD format)
        end_date: End date for indexing logbook events (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="home_assistant_indexing",
        source="connector_indexing_task",
        message=f"Starting Home Assistant indexing for connector {connector_id}",
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
            session, connector_id, SearchSourceConnectorType.HOME_ASSISTANT_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get Home Assistant credentials from the connector config
        ha_url = connector.config.get("HA_URL")
        ha_token = connector.config.get("HA_ACCESS_TOKEN")

        if not ha_url or not ha_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Home Assistant credentials not found in connector config for connector {connector_id}",
                "Missing Home Assistant credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Home Assistant credentials not found in connector config"

        # Initialize Home Assistant client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Home Assistant client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        ha_client = HomeAssistantConnector(ha_url=ha_url, access_token=ha_token)

        # Test connection
        connected, connection_error = await ha_client.test_connection()
        if not connected:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to connect to Home Assistant: {connection_error}",
                "Connection failed",
                {"error_type": "ConnectionError"},
            )
            return 0, f"Failed to connect to Home Assistant: {connection_error}"

        # Calculate date range for logbook events
        calculated_end_date = datetime.now()

        if connector.last_indexed_at:
            last_indexed_naive = (
                connector.last_indexed_at.replace(tzinfo=None)
                if connector.last_indexed_at.tzinfo
                else connector.last_indexed_at
            )

            if last_indexed_naive > calculated_end_date:
                logger.warning(
                    f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 7 days ago instead."
                )
                calculated_start_date = calculated_end_date - timedelta(days=7)
            else:
                calculated_start_date = last_indexed_naive
                logger.info(
                    f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                )
        else:
            # Default to 7 days of logbook events for initial indexing
            calculated_start_date = calculated_end_date - timedelta(days=7)
            logger.info(
                f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (7 days ago) as start date"
            )

        # Parse provided dates if available
        if start_date:
            calculated_start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            calculated_end_date = datetime.strptime(end_date, "%Y-%m-%d")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Home Assistant data from {calculated_start_date.strftime('%Y-%m-%d')} to {calculated_end_date.strftime('%Y-%m-%d')}",
            {
                "stage": "fetching_data",
                "start_date": calculated_start_date.strftime("%Y-%m-%d"),
                "end_date": calculated_end_date.strftime("%Y-%m-%d"),
            },
        )

        # Get all indexable data
        items, fetch_error = await ha_client.get_all_indexable_data(
            start_date=calculated_start_date,
            end_date=calculated_end_date,
        )

        if fetch_error:
            logger.warning(f"Some data fetch errors occurred: {fetch_error}")

        if not items:
            logger.info("No items found to index from Home Assistant")
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()

            await task_logger.log_task_success(
                log_entry,
                "No new items found to index",
                {"items_indexed": 0},
            )
            return 0, None

        await task_logger.log_task_progress(
            log_entry,
            f"Processing {len(items)} items from Home Assistant",
            {"stage": "processing_items", "total_items": len(items)},
        )

        # Process each item
        documents_indexed = 0

        for item in items:
            try:
                item_type = item.get("type", "unknown")
                entity_id = item.get("entity_id", "")
                item_name = item.get("name", "Unknown")

                # Generate unique identifier based on item type and entity_id
                if item_type == "logbook_event":
                    # For logbook events, include timestamp in unique ID
                    unique_id = f"{entity_id}_{item.get('when', '')}"
                else:
                    # For automations, scripts, scenes - use entity_id
                    unique_id = entity_id

                unique_identifier_hash = generate_unique_identifier_hash(unique_id)

                # Check for existing document
                existing_doc = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Format content to markdown
                content = ha_client.format_item_to_markdown(item)
                content_hash = generate_content_hash(content)

                # Build metadata
                metadata = {
                    "entity_id": entity_id,
                    "item_type": item_type,
                    "state": item.get("state", ""),
                    "ha_url": ha_url,
                }

                if item_type in ["automation", "script"]:
                    metadata["last_triggered"] = item.get("last_triggered", "")
                elif item_type == "logbook_event":
                    metadata["when"] = item.get("when", "")
                    metadata["domain"] = item.get("domain", "")
                    metadata["message"] = item.get("message", "")

                # Generate title
                title = f"{item_type.title()}: {item_name}"

                if existing_doc:
                    # Check if content has changed
                    if existing_doc.content_hash == content_hash:
                        logger.debug(f"Skipping unchanged item: {title}")
                        continue

                    # Update existing document
                    existing_doc.title = title
                    existing_doc.content = content
                    existing_doc.content_hash = content_hash
                    existing_doc.document_metadata = metadata

                    # Delete old chunks and create new ones
                    existing_doc.chunks.clear()

                    # Create new chunks
                    chunks = create_document_chunks(
                        content,
                        existing_doc,
                        config.chunker_instance,
                        config.embedding_model_instance,
                    )
                    for chunk in chunks:
                        existing_doc.chunks.append(chunk)

                    documents_indexed += 1
                    logger.info(f"Updated existing Home Assistant item: {title}")

                else:
                    # Create new document
                    document = Document(
                        title=title,
                        document_type=DocumentType.HOME_ASSISTANT_CONNECTOR,
                        document_metadata=metadata,
                        content=content,
                        content_hash=content_hash,
                        unique_identifier_hash=unique_identifier_hash,
                        search_space_id=search_space_id,
                    )

                    # Create chunks
                    chunks = create_document_chunks(
                        content,
                        document,
                        config.chunker_instance,
                        config.embedding_model_instance,
                    )
                    for chunk in chunks:
                        document.chunks.append(chunk)

                    session.add(document)
                    documents_indexed += 1
                    logger.info(f"Indexed new Home Assistant item: {title}")

            except Exception as e:
                logger.error(f"Error processing item {item.get('name', 'unknown')}: {e!s}")
                continue

        # Update last indexed timestamp
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Commit all changes
        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully indexed {documents_indexed} Home Assistant items",
            {"items_indexed": documents_indexed},
        )

        logger.info(f"Successfully indexed {documents_indexed} Home Assistant items")
        return documents_indexed, None

    except SQLAlchemyError as e:
        await session.rollback()
        error_message = f"Database error during Home Assistant indexing: {e!s}"
        logger.error(error_message)

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            "Database error",
            {"error_type": "DatabaseError"},
        )
        return 0, error_message

    except Exception as e:
        await session.rollback()
        error_message = f"Unexpected error during Home Assistant indexing: {e!s}"
        logger.error(error_message)

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            "Unexpected error",
            {"error_type": "UnexpectedError"},
        )
        return 0, error_message
