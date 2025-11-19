"""
Jellyfin connector indexer.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.jellyfin_connector import JellyfinConnector
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


async def index_jellyfin_data(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Jellyfin media library data.

    Args:
        session: Database session
        connector_id: ID of the Jellyfin connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (not used for Jellyfin)
        end_date: End date for indexing (not used for Jellyfin)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="jellyfin_indexing",
        source="connector_indexing_task",
        message=f"Starting Jellyfin indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.JELLYFIN_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get Jellyfin credentials from the connector config
        server_url = connector.config.get("SERVER_URL")
        api_key = connector.config.get("API_KEY")
        jellyfin_user_id = connector.config.get("USER_ID")

        if not server_url or not api_key:
            await task_logger.log_task_failure(
                log_entry,
                f"Jellyfin credentials not found in connector config for connector {connector_id}",
                "Missing Jellyfin credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Jellyfin credentials not found in connector config"

        # Initialize Jellyfin client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Jellyfin client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        jellyfin_client = JellyfinConnector(
            server_url=server_url, api_key=api_key, user_id=jellyfin_user_id
        )

        # Test connection
        connected, connection_error = await jellyfin_client.test_connection()
        if not connected:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to connect to Jellyfin: {connection_error}",
                "Connection failed",
                {"error_type": "ConnectionError"},
            )
            return 0, f"Failed to connect to Jellyfin: {connection_error}"

        await task_logger.log_task_progress(
            log_entry,
            "Fetching Jellyfin data",
            {"stage": "fetching_data"},
        )

        # Get all indexable data
        items, fetch_error = await jellyfin_client.get_all_indexable_data(
            max_items=500,
            max_favorites=100,
            max_recently_played=100,
        )

        if fetch_error:
            logger.warning(f"Some data fetch errors occurred: {fetch_error}")

        if not items:
            logger.info("No items found to index from Jellyfin")
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
            f"Processing {len(items)} items from Jellyfin",
            {"stage": "processing_items", "total_items": len(items)},
        )

        # Process each item
        documents_indexed = 0

        for item in items:
            try:
                media_item = item.get("data", {})
                source = item.get("source", "library")
                item_id = media_item.get("Id", "")
                item_type = media_item.get("Type", "Unknown")

                # Generate unique identifier based on item ID
                unique_id = f"jellyfin_{item_id}"
                unique_identifier_hash = generate_unique_identifier_hash(unique_id)

                # Check for existing document
                existing_doc = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                # Format content to markdown
                content = jellyfin_client.format_item_to_markdown(item)
                content_hash = generate_content_hash(content)

                # Build metadata
                metadata = {
                    "item_id": item_id,
                    "item_type": item_type,
                    "source": source,
                    "server_url": server_url,
                    "name": media_item.get("Name", ""),
                    "year": media_item.get("ProductionYear", ""),
                    "genres": media_item.get("Genres", []),
                    "rating": media_item.get("CommunityRating", ""),
                    "official_rating": media_item.get("OfficialRating", ""),
                }

                # Add series info for episodes
                if item_type == "Episode":
                    metadata["series_name"] = media_item.get("SeriesName", "")
                    metadata["season_number"] = media_item.get("ParentIndexNumber", "")
                    metadata["episode_number"] = media_item.get("IndexNumber", "")

                # Generate title
                name = media_item.get("Name", "Untitled")
                year = media_item.get("ProductionYear", "")
                if year:
                    title = f"{name} ({year}) - {item_type}"
                else:
                    title = f"{name} - {item_type}"

                if source == "favorite":
                    title += " [Favorite]"
                elif source == "recently_played":
                    title += " [Recently Played]"

                if existing_doc:
                    # Check if content has changed
                    if existing_doc.content_hash == content_hash:
                        logger.debug(f"Skipping unchanged item: {item_id}")
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
                    logger.info(f"Updated existing Jellyfin item: {name}")

                else:
                    # Create new document
                    document = Document(
                        title=title,
                        document_type=DocumentType.JELLYFIN_CONNECTOR,
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
                    logger.info(f"Indexed new Jellyfin item: {name}")

            except Exception as e:
                logger.error(
                    f"Error processing item {item.get('data', {}).get('Id', 'unknown')}: {e!s}"
                )
                continue

        # Update last indexed timestamp
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Commit all changes
        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully indexed {documents_indexed} Jellyfin items",
            {"items_indexed": documents_indexed},
        )

        logger.info(f"Successfully indexed {documents_indexed} Jellyfin items")
        return documents_indexed, None

    except SQLAlchemyError as e:
        await session.rollback()
        error_message = f"Database error during Jellyfin indexing: {e!s}"
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
        error_message = f"Unexpected error during Jellyfin indexing: {e!s}"
        logger.error(error_message)

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            "Unexpected error",
            {"error_type": "UnexpectedError"},
        )
        return 0, error_message
