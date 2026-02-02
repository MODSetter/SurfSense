"""
Composio connector indexer.

Routes indexing requests to toolkit-specific handlers (Google Drive, Gmail, Calendar).
Uses a registry pattern for clean, extensible connector routing.

Note: This module is intentionally placed in app/tasks/ (not in connector_indexers/)
to avoid circular import issues with the connector_indexers package.
"""

import logging
from collections.abc import Awaitable, Callable
from importlib import import_module

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.services.composio_service import INDEXABLE_TOOLKITS, TOOLKIT_TO_INDEXER
from app.services.task_logging_service import TaskLoggingService

# Type alias for heartbeat callback function
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Set up logging
logger = logging.getLogger(__name__)


# Valid Composio connector types
COMPOSIO_CONNECTOR_TYPES = {
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
}


# ============ Utility functions ============


async def get_connector_by_id(
    session: AsyncSession,
    connector_id: int,
    connector_type: SearchSourceConnectorType | None,
) -> SearchSourceConnector | None:
    """Get a connector by ID and optionally by type from the database."""
    query = select(SearchSourceConnector).filter(
        SearchSourceConnector.id == connector_id
    )
    if connector_type is not None:
        query = query.filter(SearchSourceConnector.connector_type == connector_type)
    result = await session.execute(query)
    return result.scalars().first()


def get_indexer_function(toolkit_id: str):
    """
    Dynamically import and return the indexer function for a toolkit.

    Args:
        toolkit_id: The toolkit ID (e.g., "googledrive", "gmail")

    Returns:
        Tuple of (indexer_function, supports_date_filter)

    Raises:
        ValueError: If toolkit not found in registry
    """
    if toolkit_id not in TOOLKIT_TO_INDEXER:
        raise ValueError(f"No indexer registered for toolkit: {toolkit_id}")

    module_path, function_name, supports_date_filter = TOOLKIT_TO_INDEXER[toolkit_id]
    module = import_module(module_path)
    indexer_func = getattr(module, function_name)
    return indexer_func, supports_date_filter


# ============ Main indexer function ============


async def index_composio_connector(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    max_items: int = 1000,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """
    Index content from a Composio connector.

    Routes to toolkit-specific indexing based on the connector's toolkit_id.
    Uses a registry pattern for clean, extensible connector routing.

    Args:
        session: Database session
        connector_id: ID of the Composio connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for filtering (YYYY-MM-DD format)
        end_date: End date for filtering (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp
        max_items: Maximum number of items to fetch
        on_heartbeat_callback: Optional callback to report progress for heartbeat updates

    Returns:
        Tuple of (number_of_indexed_items, number_of_skipped_items, error_message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="composio_connector_indexing",
        source="connector_indexing_task",
        message=f"Starting Composio connector indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "max_items": max_items,
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get connector by id - accept any Composio connector type
        connector = await get_connector_by_id(session, connector_id, None)

        # Validate it's a Composio connector
        if connector and connector.connector_type not in COMPOSIO_CONNECTOR_TYPES:
            error_msg = f"Connector {connector_id} is not a Composio connector"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "InvalidConnectorType"}
            )
            return 0, 0, error_msg

        if not connector:
            error_msg = f"Composio connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, error_msg

        # Get toolkit ID from config
        toolkit_id = connector.config.get("toolkit_id")
        if not toolkit_id:
            error_msg = (
                f"Composio connector {connector_id} has no toolkit_id configured"
            )
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "MissingToolkitId"}
            )
            return 0, 0, error_msg

        # Check if toolkit is indexable
        if toolkit_id not in INDEXABLE_TOOLKITS:
            error_msg = f"Toolkit '{toolkit_id}' does not support indexing yet"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ToolkitNotIndexable"}
            )
            return 0, 0, error_msg

        # Get indexer function from registry
        try:
            indexer_func, supports_date_filter = get_indexer_function(toolkit_id)
        except ValueError as e:
            await task_logger.log_task_failure(
                log_entry, str(e), {"error_type": "NoIndexerImplemented"}
            )
            return 0, 0, str(e)

        # Build kwargs for the indexer function
        kwargs = {
            "session": session,
            "connector": connector,
            "connector_id": connector_id,
            "search_space_id": search_space_id,
            "user_id": user_id,
            "task_logger": task_logger,
            "log_entry": log_entry,
            "update_last_indexed": update_last_indexed,
            "max_items": max_items,
            "on_heartbeat_callback": on_heartbeat_callback,
        }

        # Add date params for toolkits that support them
        if supports_date_filter:
            kwargs["start_date"] = start_date
            kwargs["end_date"] = end_date

        # Call the toolkit-specific indexer
        return await indexer_func(**kwargs)

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Composio indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Composio connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Composio connector: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Composio connector: {e!s}"
