"""
SearchSourceConnector routes for CRUD operations:
POST /search-source-connectors/ - Create a new connector
GET /search-source-connectors/ - List all connectors for the current user (optionally filtered by search space)
GET /search-source-connectors/{connector_id} - Get a specific connector
PUT /search-source-connectors/{connector_id} - Update a specific connector
DELETE /search-source-connectors/{connector_id} - Delete a specific connector
POST /search-source-connectors/{connector_id}/index - Index content from a connector to a search space

MCP (Model Context Protocol) Connector routes:
POST /connectors/mcp - Create a new MCP connector with custom API tools
GET /connectors/mcp - List all MCP connectors for the current user's search space
GET /connectors/mcp/{connector_id} - Get a specific MCP connector with tools config
PUT /connectors/mcp/{connector_id} - Update an MCP connector's tools config
DELETE /connectors/mcp/{connector_id} - Delete an MCP connector

Note: OAuth connectors (Gmail, Drive, Slack, etc.) support multiple accounts per search space.
Non-OAuth connectors (BookStack, GitHub, etc.) are limited to one per search space.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytz
import redis
from dateutil.parser import isoparse
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.github_connector import GitHubConnector
from app.db import (
    Permission,
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    async_session_maker,
    get_async_session,
)
from app.schemas import (
    GoogleDriveIndexRequest,
    MCPConnectorCreate,
    MCPConnectorRead,
    MCPConnectorUpdate,
    SearchSourceConnectorBase,
    SearchSourceConnectorCreate,
    SearchSourceConnectorRead,
    SearchSourceConnectorUpdate,
)
from app.services.composio_service import ComposioService
from app.services.notification_service import NotificationService
from app.tasks.connector_indexers import (
    index_airtable_records,
    index_clickup_tasks,
    index_confluence_pages,
    index_crawled_urls,
    index_discord_messages,
    index_elasticsearch_documents,
    index_github_repos,
    index_google_calendar_events,
    index_google_gmail_messages,
    index_jira_issues,
    index_linear_issues,
    index_luma_events,
    index_notion_pages,
    index_slack_messages,
)
from app.users import current_active_user
from app.utils.periodic_scheduler import (
    create_periodic_schedule,
    delete_periodic_schedule,
    update_periodic_schedule,
)
from app.utils.rbac import check_permission

# Set up logging
logger = logging.getLogger(__name__)

# Redis client for heartbeat tracking
_heartbeat_redis_client: redis.Redis | None = None

# Redis key TTL - notification is stale if no heartbeat in this time
HEARTBEAT_TTL_SECONDS = 120  # 2 minutes


def get_heartbeat_redis_client() -> redis.Redis:
    """Get or create Redis client for heartbeat tracking."""
    global _heartbeat_redis_client
    if _heartbeat_redis_client is None:
        redis_url = os.getenv(
            "REDIS_APP_URL",
            os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        )
        _heartbeat_redis_client = redis.from_url(redis_url, decode_responses=True)
    return _heartbeat_redis_client


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for notification heartbeat."""
    return f"indexing:heartbeat:{notification_id}"


router = APIRouter()


# Use Pydantic's BaseModel here
class GitHubPATRequest(BaseModel):
    github_pat: str = Field(..., description="GitHub Personal Access Token")


# --- New Endpoint to list GitHub Repositories ---
@router.post("/github/repositories", response_model=list[dict[str, Any]])
async def list_github_repositories(
    pat_request: GitHubPATRequest,
    user: User = Depends(current_active_user),  # Ensure the user is logged in
):
    """
    Fetches a list of repositories accessible by the provided GitHub PAT.
    The PAT is used for this request only and is not stored.
    """
    try:
        # Initialize GitHubConnector with the provided PAT
        github_client = GitHubConnector(token=pat_request.github_pat)
        # Fetch repositories
        repositories = github_client.get_user_repositories()
        return repositories
    except ValueError as e:
        # Handle invalid token error specifically
        logger.error(f"GitHub PAT validation failed for user {user.id}: {e!s}")
        raise HTTPException(status_code=400, detail=f"Invalid GitHub PAT: {e!s}") from e
    except Exception as e:
        logger.error(f"Failed to fetch GitHub repositories for user {user.id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch GitHub repositories."
        ) from e


@router.post("/search-source-connectors", response_model=SearchSourceConnectorRead)
async def create_search_source_connector(
    connector: SearchSourceConnectorCreate,
    search_space_id: int = Query(
        ..., description="ID of the search space to associate the connector with"
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new search source connector.
    Requires CONNECTORS_CREATE permission.

    Each search space can have only one connector of each type (based on search_space_id and connector_type).
    The config must contain the appropriate keys for the connector type.
    """
    try:
        # Check if user has permission to create connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this search space",
        )

        # Check if a connector with the same type already exists for this search space
        # (for non-OAuth connectors that don't support multiple accounts)
        # Exception: MCP_CONNECTOR can have multiple instances with different names
        if connector.connector_type != SearchSourceConnectorType.MCP_CONNECTOR:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.connector_type == connector.connector_type,
                )
            )
            existing_connector = result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {connector.connector_type} already exists in this search space.",
                )

        # Prepare connector data
        connector_data = connector.model_dump()

        # Automatically set next_scheduled_at if periodic indexing is enabled
        if (
            connector.periodic_indexing_enabled
            and connector.indexing_frequency_minutes
            and connector.next_scheduled_at is None
        ):
            connector_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=connector.indexing_frequency_minutes
            )

        db_connector = SearchSourceConnector(
            **connector_data, search_space_id=search_space_id, user_id=user.id
        )
        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        # Create periodic schedule if periodic indexing is enabled
        if (
            db_connector.periodic_indexing_enabled
            and db_connector.indexing_frequency_minutes
        ):
            success = create_periodic_schedule(
                connector_id=db_connector.id,
                search_space_id=search_space_id,
                user_id=str(user.id),
                connector_type=db_connector.connector_type,
                frequency_minutes=db_connector.indexing_frequency_minutes,
                connector_config=db_connector.config,
            )
            if not success:
                logger.warning(
                    f"Failed to create periodic schedule for connector {db_connector.id}"
                )

        return db_connector
    except ValidationError as e:
        await session.rollback()
        raise HTTPException(status_code=422, detail=f"Validation error: {e!s}") from e
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Integrity error: A connector with this type already exists in this search space. {e!s}",
        ) from e
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        logger.error(f"Failed to create search source connector: {e!s}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create search source connector: {e!s}",
        ) from e


@router.get("/search-source-connectors", response_model=list[SearchSourceConnectorRead])
async def read_search_source_connectors(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all search source connectors for a search space.
    Requires CONNECTORS_READ permission.
    """
    try:
        if search_space_id is None:
            raise HTTPException(
                status_code=400,
                detail="search_space_id is required",
            )

        # Check if user has permission to read connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this search space",
        )

        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id
        )

        result = await session.execute(query.offset(skip).limit(limit))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search source connectors: {e!s}",
        ) from e


@router.get(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def read_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific search source connector by ID.
    Requires CONNECTORS_READ permission.
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search source connector: {e!s}"
        ) from e


@router.put(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def update_search_source_connector(
    connector_id: int,
    connector_update: SearchSourceConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a search source connector.
    Requires CONNECTORS_UPDATE permission.
    Handles partial updates, including merging changes into the 'config' field.
    """
    # Get the connector first
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    db_connector = result.scalars().first()

    if not db_connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Check permission
    await check_permission(
        session,
        user,
        db_connector.search_space_id,
        Permission.CONNECTORS_UPDATE.value,
        "You don't have permission to update this connector",
    )

    # Convert the sparse update data (only fields present in request) to a dict
    update_data = connector_update.model_dump(exclude_unset=True)

    # Validate periodic indexing fields
    # Get the effective values after update
    effective_is_indexable = update_data.get("is_indexable", db_connector.is_indexable)
    effective_periodic_enabled = update_data.get(
        "periodic_indexing_enabled", db_connector.periodic_indexing_enabled
    )
    effective_frequency = update_data.get(
        "indexing_frequency_minutes", db_connector.indexing_frequency_minutes
    )

    # Validate periodic indexing configuration
    if effective_periodic_enabled:
        if not effective_is_indexable:
            raise HTTPException(
                status_code=422,
                detail="periodic_indexing_enabled can only be True for indexable connectors",
            )
        if effective_frequency is None:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes is required when periodic_indexing_enabled is True",
            )
        if effective_frequency <= 0:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes must be greater than 0",
            )

        # Automatically set next_scheduled_at if not provided and periodic indexing is being enabled
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ) and "next_scheduled_at" not in update_data:
            # Schedule the next indexing based on the frequency
            update_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=effective_frequency
            )
    elif (
        effective_periodic_enabled is False
        and "periodic_indexing_enabled" in update_data
    ):
        # If disabling periodic indexing, clear the next_scheduled_at
        update_data["next_scheduled_at"] = None

    # Special handling for 'config' field
    if "config" in update_data:
        incoming_config = update_data["config"]  # Config data from the request
        existing_config = (
            db_connector.config if db_connector.config else {}
        )  # Current config from DB

        # Merge incoming config into existing config
        # This preserves existing keys (like GITHUB_PAT) if they are not in the incoming data
        merged_config = existing_config.copy()
        merged_config.update(incoming_config)

        # -- Validation after merging --
        # Validate the *merged* config based on the connector type
        # We need the connector type - use the one from the update if provided, else the existing one
        current_connector_type = (
            connector_update.connector_type
            if connector_update.connector_type is not None
            else db_connector.connector_type
        )

        try:
            # We can reuse the base validator by creating a temporary base model instance
            # Note: This assumes 'name' and 'is_indexable' are not crucial for config validation itself
            temp_data_for_validation = {
                "name": db_connector.name,  # Use existing name
                "connector_type": current_connector_type,
                "is_indexable": db_connector.is_indexable,  # Use existing value
                "last_indexed_at": db_connector.last_indexed_at,  # Not used by validator
                "config": merged_config,
            }
            SearchSourceConnectorBase.model_validate(temp_data_for_validation)
        except ValidationError as e:
            # Raise specific validation error for the merged config
            raise HTTPException(
                status_code=422, detail=f"Validation error for merged config: {e!s}"
            ) from e

        # If validation passes, update the main update_data dict with the merged config
        update_data["config"] = merged_config

    # Apply all updates (including the potentially merged config)
    for key, value in update_data.items():
        # Prevent changing connector_type if it causes a duplicate (check moved here)
        if key == "connector_type" and value != db_connector.connector_type:
            check_result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id
                    == db_connector.search_space_id,
                    SearchSourceConnector.connector_type == value,
                    SearchSourceConnector.id != connector_id,
                )
            )
            existing_connector = check_result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {value} already exists in this search space.",
                )

        setattr(db_connector, key, value)

    try:
        await session.commit()
        await session.refresh(db_connector)

        # Handle periodic schedule updates
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ):
            if (
                db_connector.periodic_indexing_enabled
                and db_connector.indexing_frequency_minutes
            ):
                # Create or update the periodic schedule
                success = update_periodic_schedule(
                    connector_id=db_connector.id,
                    search_space_id=db_connector.search_space_id,
                    user_id=str(user.id),
                    connector_type=db_connector.connector_type,
                    frequency_minutes=db_connector.indexing_frequency_minutes,
                )
                if not success:
                    logger.warning(
                        f"Failed to update periodic schedule for connector {db_connector.id}"
                    )
            else:
                # Delete the periodic schedule if disabled
                success = delete_periodic_schedule(db_connector.id)
                if not success:
                    logger.warning(
                        f"Failed to delete periodic schedule for connector {db_connector.id}"
                    )

        return db_connector
    except IntegrityError as e:
        await session.rollback()
        # This might occur if connector_type constraint is violated somehow after the check
        raise HTTPException(
            status_code=409, detail=f"Database integrity error during update: {e!s}"
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to update search source connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update search source connector: {e!s}",
        ) from e


@router.delete("/search-source-connectors/{connector_id}", response_model=dict)
async def delete_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a search source connector and all its associated documents.

    The deletion runs in background via Celery task. User is notified
    via the notification system when complete (no polling required).

    Requires CONNECTORS_DELETE permission.
    """
    from app.tasks.celery_tasks.connector_deletion_task import (
        delete_connector_with_documents_task,
    )

    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        db_connector = result.scalars().first()

        if not db_connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            user,
            db_connector.search_space_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        # Store connector info before we queue the deletion task
        connector_name = db_connector.name
        connector_type = db_connector.connector_type.value
        search_space_id = db_connector.search_space_id

        # Delete any periodic schedule associated with this connector (lightweight, sync)
        if db_connector.periodic_indexing_enabled:
            success = delete_periodic_schedule(connector_id)
            if not success:
                logger.warning(
                    f"Failed to delete periodic schedule for connector {connector_id}"
                )

        # For Composio connectors, delete the connected account in Composio (lightweight API call, sync)
        composio_connector_types = [
            SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        ]
        if db_connector.connector_type in composio_connector_types:
            composio_connected_account_id = db_connector.config.get(
                "composio_connected_account_id"
            )
            if composio_connected_account_id and ComposioService.is_enabled():
                try:
                    service = ComposioService()
                    deleted = await service.delete_connected_account(
                        composio_connected_account_id
                    )
                    if deleted:
                        logger.info(
                            f"Successfully deleted Composio connected account {composio_connected_account_id} "
                            f"for connector {connector_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to delete Composio connected account {composio_connected_account_id} "
                            f"for connector {connector_id}"
                        )
                except Exception as composio_error:
                    # Log but don't fail the deletion - Composio account may already be deleted
                    logger.warning(
                        f"Error deleting Composio connected account {composio_connected_account_id}: {composio_error!s}"
                    )

        # Queue background task to delete documents and connector
        # This handles potentially large document counts without blocking the API
        delete_connector_with_documents_task.delay(
            connector_id=connector_id,
            user_id=str(user.id),
            search_space_id=search_space_id,
            connector_name=connector_name,
            connector_type=connector_type,
        )

        logger.info(
            f"Queued deletion task for connector {connector_id} ({connector_name})"
        )

        return {
            "message": "Connector deletion started. You will be notified when complete.",
            "status": "queued",
            "connector_id": connector_id,
            "connector_name": connector_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start connector deletion: {e!s}",
        ) from e


@router.post(
    "/search-source-connectors/{connector_id}/index", response_model=dict[str, Any]
)
async def index_connector_content(
    connector_id: int,
    search_space_id: int = Query(
        ..., description="ID of the search space to store indexed content"
    ),
    start_date: str = Query(
        None,
        description="Start date for indexing (YYYY-MM-DD format). If not provided, uses last_indexed_at or defaults to 365 days ago",
    ),
    end_date: str = Query(
        None,
        description="End date for indexing (YYYY-MM-DD format). If not provided, uses today's date. For calendar connectors (Google Calendar, Luma), future dates can be selected to index upcoming events.",
    ),
    drive_items: GoogleDriveIndexRequest | None = Body(
        None,
        description="[Google Drive only] Structured request with folders and files to index",
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Index content from a connector to a search space.
    Requires CONNECTORS_UPDATE permission (to trigger indexing).

    Currently supports:
    - SLACK_CONNECTOR: Indexes messages from all accessible Slack channels
    - TEAMS_CONNECTOR: Indexes messages from all accessible Microsoft Teams channels
    - NOTION_CONNECTOR: Indexes pages from all accessible Notion pages
    - GITHUB_CONNECTOR: Indexes code and documentation from GitHub repositories
    - LINEAR_CONNECTOR: Indexes issues and comments from Linear
    - JIRA_CONNECTOR: Indexes issues and comments from Jira
    - DISCORD_CONNECTOR: Indexes messages from all accessible Discord channels
    - LUMA_CONNECTOR: Indexes events from Luma
    - ELASTICSEARCH_CONNECTOR: Indexes documents from Elasticsearch
    - WEBCRAWLER_CONNECTOR: Indexes web pages from crawled websites

    Args:
        connector_id: ID of the connector to use
        search_space_id: ID of the search space to store indexed content

    Returns:
        Dictionary with indexing status
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check if user has permission to update connectors (indexing is an update operation)
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to index content in this search space",
        )

        # Handle different connector types
        response_message = ""
        indexing_started = True
        # Use UTC for consistency with last_indexed_at storage
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Determine the actual date range to use
        if start_date is None:
            # Use last_indexed_at or default to 365 days ago
            if connector.last_indexed_at:
                # Convert last_indexed_at to timezone-naive for comparison (like calculate_date_range does)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )
                # Use UTC for "today" to match how last_indexed_at is stored
                today_utc = datetime.now(UTC).replace(tzinfo=None).date()
                last_indexed_date = last_indexed_naive.date()

                if last_indexed_date == today_utc:
                    # If last indexed today, go back 1 day to ensure we don't miss anything
                    indexing_from = (today_utc - timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    indexing_from = last_indexed_naive.strftime("%Y-%m-%d")
            else:
                indexing_from = (
                    datetime.now(UTC).replace(tzinfo=None) - timedelta(days=365)
                ).strftime("%Y-%m-%d")
        else:
            indexing_from = start_date

        # For calendar connectors, default to today but allow future dates if explicitly provided
        if connector.connector_type in [
            SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
            SearchSourceConnectorType.LUMA_CONNECTOR,
        ]:
            # Default to today if no end_date provided (users can manually select future dates)
            indexing_to = today_str if end_date is None else end_date

            # If start_date and end_date are the same, adjust end_date to be one day later
            # to ensure valid date range (start_date must be strictly before end_date)
            if indexing_from == indexing_to:
                dt = isoparse(indexing_to)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=pytz.UTC)
                else:
                    dt = dt.astimezone(pytz.UTC)
                # Add one day to end_date to make it strictly after start_date
                dt_end = dt + timedelta(days=1)
                indexing_to = dt_end.strftime("%Y-%m-%d")
                logger.info(
                    f"Adjusted end_date from {end_date} to {indexing_to} "
                    f"to ensure valid date range (start_date must be strictly before end_date)"
                )
        else:
            # For non-calendar connectors, cap at today
            indexing_to = end_date if end_date else today_str

        if connector.connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_slack_messages_task,
            )

            logger.info(
                f"Triggering Slack indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_slack_messages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Slack indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.TEAMS_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_teams_messages_task,
            )

            logger.info(
                f"Triggering Teams indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_teams_messages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Teams indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_notion_pages_task

            logger.info(
                f"Triggering Notion indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_notion_pages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Notion indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_github_repos_task

            logger.info(
                f"Triggering GitHub indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_github_repos_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "GitHub indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.LINEAR_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_linear_issues_task

            logger.info(
                f"Triggering Linear indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_linear_issues_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Linear indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.JIRA_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_jira_issues_task

            logger.info(
                f"Triggering Jira indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_jira_issues_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Jira indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.CONFLUENCE_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_confluence_pages_task,
            )

            logger.info(
                f"Triggering Confluence indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_confluence_pages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Confluence indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.BOOKSTACK_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_bookstack_pages_task,
            )

            logger.info(
                f"Triggering BookStack indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_bookstack_pages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "BookStack indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.CLICKUP_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_clickup_tasks_task

            logger.info(
                f"Triggering ClickUp indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_clickup_tasks_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "ClickUp indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_calendar_events_task,
            )

            logger.info(
                f"Triggering Google Calendar indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_google_calendar_events_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Google Calendar indexing started in the background."
        elif connector.connector_type == SearchSourceConnectorType.AIRTABLE_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_airtable_records_task,
            )

            logger.info(
                f"Triggering Airtable indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_airtable_records_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Airtable indexing started in the background."
        elif (
            connector.connector_type == SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_gmail_messages_task,
            )

            logger.info(
                f"Triggering Google Gmail indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_google_gmail_messages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Google Gmail indexing started in the background."

        elif (
            connector.connector_type == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_drive_files_task,
            )

            if not drive_items or not drive_items.has_items():
                raise HTTPException(
                    status_code=400,
                    detail="Google Drive indexing requires drive_items body parameter with folders or files",
                )

            logger.info(
                f"Triggering Google Drive indexing for connector {connector_id} into search space {search_space_id}, "
                f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
            )

            # Pass structured data to Celery task
            index_google_drive_files_task.delay(
                connector_id,
                search_space_id,
                str(user.id),
                drive_items.model_dump(),  # Convert to dict for JSON serialization
            )
            response_message = "Google Drive indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.DISCORD_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_discord_messages_task,
            )

            logger.info(
                f"Triggering Discord indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_discord_messages_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Discord indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.LUMA_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_luma_events_task

            logger.info(
                f"Triggering Luma indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_luma_events_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Luma indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_elasticsearch_documents_task,
            )

            logger.info(
                f"Triggering Elasticsearch indexing for connector {connector_id} into search space {search_space_id}"
            )
            index_elasticsearch_documents_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Elasticsearch indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.WEBCRAWLER_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_crawled_urls_task
            from app.utils.webcrawler_utils import parse_webcrawler_urls

            # Check if URLs are configured before triggering indexing
            connector_config = connector.config or {}
            urls = parse_webcrawler_urls(connector_config.get("INITIAL_URLS"))

            if not urls:
                # URLs are optional - skip indexing gracefully
                logger.info(
                    f"Webcrawler connector {connector_id} has no URLs configured, skipping indexing"
                )
                response_message = "No URLs configured for this connector. Add URLs in the connector settings to enable indexing."
                indexing_started = False
            else:
                logger.info(
                    f"Triggering web pages indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
                )
                index_crawled_urls_task.delay(
                    connector_id,
                    search_space_id,
                    str(user.id),
                    indexing_from,
                    indexing_to,
                )
                response_message = "Web page indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.OBSIDIAN_CONNECTOR:
            from app.config import config as app_config
            from app.tasks.celery_tasks.connector_tasks import index_obsidian_vault_task

            # Obsidian connector only available in self-hosted mode
            if not app_config.is_self_hosted():
                raise HTTPException(
                    status_code=400,
                    detail="Obsidian connector is only available in self-hosted mode",
                )

            logger.info(
                f"Triggering Obsidian vault indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_obsidian_vault_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Obsidian vault indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_composio_connector_task,
            )

            # For Composio Google Drive, if drive_items is provided, update connector config
            # This allows the UI to pass folder/file selection like the regular Google Drive connector
            if drive_items and drive_items.has_items():
                # Update connector config with the selected folders/files
                config = connector.config or {}
                config["selected_folders"] = [
                    {"id": f.id, "name": f.name} for f in drive_items.folders
                ]
                config["selected_files"] = [
                    {"id": f.id, "name": f.name} for f in drive_items.files
                ]
                if drive_items.indexing_options:
                    config["indexing_options"] = {
                        "max_files_per_folder": drive_items.indexing_options.max_files_per_folder,
                        "incremental_sync": drive_items.indexing_options.incremental_sync,
                        "include_subfolders": drive_items.indexing_options.include_subfolders,
                    }
                connector.config = config
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(connector, "config")
                await session.commit()
                await session.refresh(connector)

                logger.info(
                    f"Triggering Composio Google Drive indexing for connector {connector_id} into search space {search_space_id}, "
                    f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
                )
            else:
                logger.info(
                    f"Triggering Composio Google Drive indexing for connector {connector_id} into search space {search_space_id} "
                    f"using existing config (from {indexing_from} to {indexing_to})"
                )

            index_composio_connector_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = (
                "Composio Google Drive indexing started in the background."
            )

        elif connector.connector_type in [
            SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        ]:
            from app.tasks.celery_tasks.connector_tasks import (
                index_composio_connector_task,
            )

            # For Composio Gmail and Calendar, use the same date calculation logic as normal connectors
            # This ensures consistent behavior and uses last_indexed_at to reduce API calls
            # (includes special case: if indexed today, go back 1 day to avoid missing data)
            logger.info(
                f"Triggering Composio connector indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_composio_connector_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Composio connector indexing started in the background."

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Indexing not supported for connector type: {connector.connector_type}",
            )

        return {
            "message": response_message,
            "indexing_started": indexing_started,
            "connector_id": connector_id,
            "search_space_id": search_space_id,
            "indexing_from": indexing_from,
            "indexing_to": indexing_to,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to initiate indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate indexing: {e!s}"
        ) from e


async def _update_connector_timestamp_by_id(session: AsyncSession, connector_id: int):
    """
    Update the last_indexed_at timestamp for a connector by its ID.
    Internal helper function for routes.

    Args:
        session: Database session
        connector_id: ID of the connector to update
    """
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if connector:
            connector.last_indexed_at = datetime.now(
                UTC
            )  # Use UTC for timezone consistency
            await session.commit()
            logger.info(f"Updated last_indexed_at for connector {connector_id}")
    except Exception as e:
        logger.error(
            f"Failed to update last_indexed_at for connector {connector_id}: {e!s}"
        )
        await session.rollback()


async def run_slack_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Slack indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_slack_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_slack_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Slack indexing.

    Args:
        session: Database session
        connector_id: ID of the Slack connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_slack_messages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def _run_indexing_with_notifications(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
    indexing_function,
    update_timestamp_func=None,
    supports_retry_callback: bool = False,
    supports_heartbeat_callback: bool = False,
):
    """
    Generic helper to run indexing with real-time notifications.

    Args:
        session: Database session
        connector_id: ID of the connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
        indexing_function: Async function that performs the indexing
        update_timestamp_func: Optional function to update connector timestamp
        supports_retry_callback: Whether the indexing function supports on_retry_callback
        supports_heartbeat_callback: Whether the indexing function supports on_heartbeat_callback
    """
    from uuid import UUID

    from celery.exceptions import SoftTimeLimitExceeded

    notification = None
    # Track indexed count for retry notifications and heartbeat
    current_indexed_count = 0

    try:
        # Get connector info for notification
        connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()

        if connector:
            # Create notification when indexing starts
            notification = (
                await NotificationService.connector_indexing.notify_indexing_started(
                    session=session,
                    user_id=UUID(user_id),
                    connector_id=connector_id,
                    connector_name=connector.name,
                    connector_type=connector.connector_type.value,
                    search_space_id=search_space_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

            # Set initial Redis heartbeat for stale detection
            if notification:
                try:
                    heartbeat_key = _get_heartbeat_key(notification.id)
                    get_heartbeat_redis_client().setex(
                        heartbeat_key, HEARTBEAT_TTL_SECONDS, "0"
                    )
                except Exception as e:
                    logger.warning(f"Failed to set initial Redis heartbeat: {e}")

        # Update notification to fetching stage
        if notification:
            await NotificationService.connector_indexing.notify_indexing_progress(
                session=session,
                notification=notification,
                indexed_count=0,
                stage="fetching",
            )

        # Create retry callback for connectors that support it
        async def on_retry_callback(
            retry_reason: str, attempt: int, max_attempts: int, wait_seconds: float
        ) -> None:
            """Callback to update notification during API retries (rate limits, etc.)"""
            nonlocal notification
            if notification:
                try:
                    await session.refresh(notification)
                    await NotificationService.connector_indexing.notify_retry_progress(
                        session=session,
                        notification=notification,
                        indexed_count=current_indexed_count,
                        retry_reason=retry_reason,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        wait_seconds=wait_seconds,
                    )
                    await session.commit()
                except Exception as e:
                    # Don't let notification errors break the indexing
                    logger.warning(f"Failed to update retry notification: {e}")

        # Create heartbeat callback for connectors that support it
        # This updates the notification periodically during long-running indexing loops
        # to prevent the task from appearing stuck if the worker crashes
        async def on_heartbeat_callback(indexed_count: int) -> None:
            """Callback to update notification during indexing (heartbeat)."""
            nonlocal notification, current_indexed_count
            current_indexed_count = indexed_count
            if notification:
                try:
                    # Set Redis heartbeat key with TTL (fast, for stale detection)
                    heartbeat_key = _get_heartbeat_key(notification.id)
                    get_heartbeat_redis_client().setex(
                        heartbeat_key, HEARTBEAT_TTL_SECONDS, str(indexed_count)
                    )
                except Exception as e:
                    # Don't let Redis errors break the indexing
                    logger.warning(f"Failed to set Redis heartbeat: {e}")

                try:
                    # Still update DB notification for progress display
                    await session.refresh(notification)
                    await (
                        NotificationService.connector_indexing.notify_indexing_progress(
                            session=session,
                            notification=notification,
                            indexed_count=indexed_count,
                            stage="processing",
                        )
                    )
                    await session.commit()
                except Exception as e:
                    # Don't let notification errors break the indexing
                    logger.warning(f"Failed to update heartbeat notification: {e}")

        # Build kwargs for indexing function
        indexing_kwargs = {
            "session": session,
            "connector_id": connector_id,
            "search_space_id": search_space_id,
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
            "update_last_indexed": False,
        }

        # Add retry callback for connectors that support it
        if supports_retry_callback:
            indexing_kwargs["on_retry_callback"] = on_retry_callback

        # Add heartbeat callback for connectors that support it
        if supports_heartbeat_callback:
            indexing_kwargs["on_heartbeat_callback"] = on_heartbeat_callback

        # Run the indexing function
        # Some indexers return (indexed, error), others return (indexed, skipped, error)
        result = await indexing_function(**indexing_kwargs)

        # Handle both 2-tuple and 3-tuple returns for backwards compatibility
        if len(result) == 3:
            documents_processed, documents_skipped, error_or_warning = result
        else:
            documents_processed, error_or_warning = result
            documents_skipped = None

        # Update connector timestamp if function provided and indexing was successful
        if documents_processed > 0 and update_timestamp_func:
            # Update notification to storing stage
            if notification:
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    stage="storing",
                )

            await update_timestamp_func(session, connector_id)
            await session.commit()  # Commit timestamp update
            logger.info(
                f"Indexing completed successfully: {documents_processed} documents processed"
            )

            # Update notification on success (or partial success with errors)
            if notification:
                # Refresh notification to ensure it's not stale after timestamp update commit
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    error_message=error_or_warning,  # Show errors even if some documents were indexed
                    skipped_count=documents_skipped,
                )
                await (
                    session.commit()
                )  # Commit to ensure Electric SQL syncs the notification update
        elif documents_processed > 0:
            # Update notification to storing stage
            if notification:
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    stage="storing",
                )

            # Success but no timestamp update function
            logger.info(
                f"Indexing completed successfully: {documents_processed} documents processed"
            )
            if notification:
                # Refresh notification to ensure it's not stale after indexing function commits
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    error_message=error_or_warning,  # Show errors even if some documents were indexed
                    skipped_count=documents_skipped,
                )
                await (
                    session.commit()
                )  # Commit to ensure Electric SQL syncs the notification update
        else:
            # No new documents processed - check if this is an error or just no changes
            if error_or_warning:
                # Check if this is a duplicate warning or empty result (success cases) or an actual error
                # Handle both normal and Composio calendar connectors
                error_or_warning_lower = (
                    str(error_or_warning).lower() if error_or_warning else ""
                )
                is_duplicate_warning = "skipped (duplicate)" in error_or_warning_lower
                # "No X found" messages are success cases - sync worked, just found nothing in date range
                is_empty_result = (
                    "no " in error_or_warning_lower
                    and "found" in error_or_warning_lower
                )
                # Informational warnings - sync succeeded but some content couldn't be synced
                # These are NOT errors, just notifications about API limitations or recommendations
                is_info_warning = (
                    "couldn't be synced" in error_or_warning_lower
                    or "using legacy token" in error_or_warning_lower
                    or "(api limitation)" in error_or_warning_lower
                )

                if is_duplicate_warning or is_empty_result or is_info_warning:
                    # These are success cases - sync worked, just found nothing new
                    logger.info(f"Indexing completed successfully: {error_or_warning}")
                    # Still update timestamp so ElectricSQL syncs and clears "Syncing" UI
                    if update_timestamp_func:
                        await update_timestamp_func(session, connector_id)
                        await session.commit()  # Commit timestamp update
                    if notification:
                        # Refresh notification to ensure it's not stale after timestamp update commit
                        await session.refresh(notification)
                        # For empty results, use a cleaner message
                        notification_message = (
                            "No new items found in date range"
                            if is_empty_result
                            else error_or_warning
                        )
                        await NotificationService.connector_indexing.notify_indexing_completed(
                            session=session,
                            notification=notification,
                            indexed_count=0,
                            error_message=notification_message,  # Pass as warning, not error
                            is_warning=True,  # Flag to indicate this is a warning, not an error
                            skipped_count=documents_skipped,
                        )
                        await (
                            session.commit()
                        )  # Commit to ensure Electric SQL syncs the notification update
                else:
                    # Actual failure
                    logger.error(f"Indexing failed: {error_or_warning}")
                    if notification:
                        # Refresh notification to ensure it's not stale after indexing function commits
                        await session.refresh(notification)
                        await NotificationService.connector_indexing.notify_indexing_completed(
                            session=session,
                            notification=notification,
                            indexed_count=0,
                            error_message=error_or_warning,
                            skipped_count=documents_skipped,
                        )
                        await (
                            session.commit()
                        )  # Commit to ensure Electric SQL syncs the notification update
            else:
                # Success - just no new documents to index (all skipped/unchanged)
                logger.info(
                    "Indexing completed: No new documents to process (all up to date)"
                )
                # Still update timestamp so ElectricSQL syncs and clears "Syncing" UI
                if update_timestamp_func:
                    await update_timestamp_func(session, connector_id)
                    await session.commit()  # Commit timestamp update
                if notification:
                    # Refresh notification to ensure it's not stale after timestamp update commit
                    await session.refresh(notification)
                    await NotificationService.connector_indexing.notify_indexing_completed(
                        session=session,
                        notification=notification,
                        indexed_count=0,
                        error_message=None,  # No error - sync succeeded
                        skipped_count=documents_skipped,
                    )
                    await (
                        session.commit()
                    )  # Commit to ensure Electric SQL syncs the notification update
    except SoftTimeLimitExceeded:
        # Celery soft time limit was reached - task is about to be killed
        # Gracefully save progress and mark as interrupted
        logger.warning(
            f"Soft time limit reached for connector {connector_id}. "
            f"Saving partial progress: {current_indexed_count} items indexed."
        )

        if notification:
            try:
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=current_indexed_count,
                    error_message="Time limit reached. Partial sync completed. Please run again for remaining items.",
                    is_warning=True,  # Mark as warning since partial data was indexed
                )
                await session.commit()
            except Exception as notif_error:
                logger.error(
                    f"Failed to update notification on soft timeout: {notif_error!s}"
                )

        # Re-raise so Celery knows the task was terminated
        raise
    except Exception as e:
        logger.error(f"Error in indexing task: {e!s}", exc_info=True)

        # Update notification on exception
        if notification:
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=current_indexed_count,  # Use tracked count, not 0
                    error_message=str(e),
                    skipped_count=None,  # Unknown on exception
                )
            except Exception as notif_error:
                logger.error(f"Failed to update notification: {notif_error!s}")
    finally:
        # Clean up Redis heartbeat key when task completes (success or failure)
        if notification:
            try:
                heartbeat_key = _get_heartbeat_key(notification.id)
                get_heartbeat_redis_client().delete(heartbeat_key)
            except Exception:
                pass  # Ignore cleanup errors - key will expire anyway


async def run_notion_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Notion indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await _run_indexing_with_notifications(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            indexing_function=index_notion_pages,
            update_timestamp_func=_update_connector_timestamp_by_id,
            supports_retry_callback=True,  # Notion connector supports retry notifications
            supports_heartbeat_callback=True,  # Notion connector supports heartbeat notifications
        )


async def run_notion_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Notion indexing.

    Args:
        session: Database session
        connector_id: ID of the Notion connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_notion_pages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_retry_callback=True,  # Notion connector supports retry notifications
        supports_heartbeat_callback=True,  # Notion connector supports heartbeat notifications
    )


# Add new helper functions for GitHub indexing
async def run_github_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run GitHub indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing GitHub connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_github_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing GitHub connector {connector_id}")


async def run_github_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run GitHub indexing.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_github_repos,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Linear indexing
async def run_linear_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Linear indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Linear connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_linear_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing Linear connector {connector_id}")


async def run_linear_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Linear indexing.

    Args:
        session: Database session
        connector_id: ID of the Linear connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_linear_issues,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for discord indexing
async def run_discord_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Discord indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_discord_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_discord_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Discord indexing.

    Args:
        session: Database session
        connector_id: ID of the Discord connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_discord_messages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def run_teams_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Microsoft Teams indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_teams_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_teams_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Microsoft Teams indexing.

    Args:
        session: Database session
        connector_id: ID of the Teams connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers.teams_indexer import index_teams_messages

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_teams_messages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Jira indexing
async def run_jira_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Jira indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Jira connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_jira_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing Jira connector {connector_id}")


async def run_jira_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Jira indexing.

    Args:
        session: Database session
        connector_id: ID of the Jira connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_jira_issues,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Confluence indexing
async def run_confluence_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Confluence indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Confluence connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_confluence_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(
        f"Background task finished: Indexing Confluence connector {connector_id}"
    )


async def run_confluence_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Confluence indexing.

    Args:
        session: Database session
        connector_id: ID of the Confluence connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_confluence_pages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for ClickUp indexing
async def run_clickup_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run ClickUp indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing ClickUp connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_clickup_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing ClickUp connector {connector_id}")


async def run_clickup_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run ClickUp indexing.

    Args:
        session: Database session
        connector_id: ID of the ClickUp connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_clickup_tasks,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Airtable indexing
async def run_airtable_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Airtable indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Airtable connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_airtable_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing Airtable connector {connector_id}")


async def run_airtable_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Airtable indexing.

    Args:
        session: Database session
        connector_id: ID of the Airtable connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_airtable_records,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Google Calendar indexing
async def run_google_calendar_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Google Calendar indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Google Calendar connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_google_calendar_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(
        f"Background task finished: Indexing Google Calendar connector {connector_id}"
    )


async def run_google_calendar_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Google Calendar indexing.

    Args:
        session: Database session
        connector_id: ID of the Google Calendar connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_google_calendar_events,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def run_google_gmail_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Google Gmail indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_google_gmail_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_google_gmail_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Google Gmail indexing.

    Args:
        session: Database session
        connector_id: ID of the Google Gmail connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """

    # Create a wrapper function that calls index_google_gmail_messages with max_messages
    async def gmail_indexing_wrapper(
        session: AsyncSession,
        connector_id: int,
        search_space_id: int,
        user_id: str,
        start_date: str | None,
        end_date: str | None,
        update_last_indexed: bool,
    ) -> tuple[int, str | None]:
        # Use a reasonable default for max_messages
        max_messages = 1000
        indexed_count, error_message = await index_google_gmail_messages(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=update_last_indexed,
            max_messages=max_messages,
        )
        # index_google_gmail_messages returns (int, str) but we need (int, str | None)
        return indexed_count, error_message if error_message else None

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=gmail_indexing_wrapper,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def run_google_drive_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    items_dict: dict,  # Dictionary with 'folders', 'files', and 'indexing_options'
):
    """Runs the Google Drive indexing task for folders and files with notifications."""
    from uuid import UUID

    notification = None
    try:
        from app.tasks.connector_indexers.google_drive_indexer import (
            index_google_drive_files,
            index_google_drive_single_file,
        )

        # Parse the structured data
        items = GoogleDriveIndexRequest(**items_dict)
        indexing_options = items.indexing_options
        total_indexed = 0
        errors = []

        # Get connector info for notification
        connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()

        if connector:
            # Create notification when indexing starts
            notification = await NotificationService.connector_indexing.notify_google_drive_indexing_started(
                session=session,
                user_id=UUID(user_id),
                connector_id=connector_id,
                connector_name=connector.name,
                connector_type=connector.connector_type.value,
                search_space_id=search_space_id,
                folder_count=len(items.folders),
                file_count=len(items.files),
                folder_names=items.get_folder_names() if items.folders else None,
                file_names=items.get_file_names() if items.files else None,
            )

        # Update notification to fetching stage
        if notification:
            await NotificationService.connector_indexing.notify_indexing_progress(
                session=session,
                notification=notification,
                indexed_count=0,
                stage="fetching",
            )

        # Index each folder with indexing options
        for folder in items.folders:
            try:
                indexed_count, error_message = await index_google_drive_files(
                    session,
                    connector_id,
                    search_space_id,
                    user_id,
                    folder_id=folder.id,
                    folder_name=folder.name,
                    use_delta_sync=indexing_options.incremental_sync,
                    update_last_indexed=False,
                    max_files=indexing_options.max_files_per_folder,
                    include_subfolders=indexing_options.include_subfolders,
                )
                if error_message:
                    errors.append(f"Folder '{folder.name}': {error_message}")
                else:
                    total_indexed += indexed_count
            except Exception as e:
                errors.append(f"Folder '{folder.name}': {e!s}")
                logger.error(
                    f"Error indexing folder {folder.name} ({folder.id}): {e}",
                    exc_info=True,
                )

        # Index each individual file
        for file in items.files:
            try:
                indexed_count, error_message = await index_google_drive_single_file(
                    session,
                    connector_id,
                    search_space_id,
                    user_id,
                    file_id=file.id,
                    file_name=file.name,
                )
                if error_message:
                    errors.append(f"File '{file.name}': {error_message}")
                else:
                    total_indexed += indexed_count
            except Exception as e:
                errors.append(f"File '{file.name}': {e!s}")
                logger.error(
                    f"Error indexing file {file.name} ({file.id}): {e}",
                    exc_info=True,
                )

        # Prepare error message for notification
        error_message = None
        if errors:
            error_message = "; ".join(errors)
            logger.error(
                f"Google Drive indexing completed with errors for connector {connector_id}: {error_message}"
            )
        else:
            # Update notification to storing stage
            if notification:
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=total_indexed,
                    stage="storing",
                )

            logger.info(
                f"Google Drive indexing successful for connector {connector_id}. Indexed {total_indexed} documents from {len(items.folders)} folder(s) and {len(items.files)} file(s)."
            )
            # Update the last indexed timestamp only on full success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update

        # Update notification on completion
        if notification:
            # Refresh notification to reload attributes that may have been expired by earlier commits
            await session.refresh(notification)
            await NotificationService.connector_indexing.notify_indexing_completed(
                session=session,
                notification=notification,
                indexed_count=total_indexed,
                error_message=error_message,
            )

    except Exception as e:
        logger.error(
            f"Critical error in run_google_drive_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )

        # Update notification on exception
        if notification:
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=0,
                    error_message=str(e),
                )
            except Exception as notif_error:
                logger.error(f"Failed to update notification: {notif_error!s}")


# Add new helper functions for luma indexing
async def run_luma_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Luma indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_luma_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_luma_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Luma indexing.

    Args:
        session: Database session
        connector_id: ID of the Luma connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_luma_events,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def run_elasticsearch_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Elasticsearch indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Elasticsearch connector {connector_id} into space {search_space_id}"
    )
    async with async_session_maker() as session:
        await run_elasticsearch_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(
        f"Background task finished: Indexing Elasticsearch connector {connector_id}"
    )


async def run_elasticsearch_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Elasticsearch indexing.

    Args:
        session: Database session
        connector_id: ID of the Elasticsearch connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_elasticsearch_documents,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for crawled web page indexing
async def run_web_page_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Web page indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_web_page_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_web_page_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Web page indexing.

    Args:
        session: Database session
        connector_id: ID of the webcrawler connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_crawled_urls,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for BookStack indexing
async def run_bookstack_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run BookStack indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing BookStack connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_bookstack_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(
        f"Background task finished: Indexing BookStack connector {connector_id}"
    )


async def run_bookstack_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run BookStack indexing.

    Args:
        session: Database session
        connector_id: ID of the BookStack connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_bookstack_pages

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_bookstack_pages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# Add new helper functions for Obsidian indexing
async def run_obsidian_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Obsidian indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Obsidian connector {connector_id} into space {search_space_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_obsidian_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing Obsidian connector {connector_id}")


async def run_obsidian_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Obsidian vault indexing.

    Args:
        session: Database session
        connector_id: ID of the Obsidian connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_obsidian_vault

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_obsidian_vault,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


async def run_composio_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Composio indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_composio_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


async def run_composio_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None,
    end_date: str | None,
):
    """
    Run Composio connector indexing with real-time notifications.

    This wraps the Composio indexer with the notification system so that
    Electric SQL can sync indexing progress to the frontend in real-time.

    Args:
        session: Database session
        connector_id: ID of the Composio connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.composio_indexer import index_composio_connector

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_composio_connector,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


# =============================================================================
# MCP Connector Routes
# =============================================================================


@router.post("/connectors/mcp", response_model=MCPConnectorRead, status_code=201)
async def create_mcp_connector(
    connector_data: MCPConnectorCreate,
    search_space_id: int = Query(..., description="Search space ID"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new MCP (Model Context Protocol) connector.

    MCP connectors allow users to connect to MCP servers (like in Cursor).
    Tools are auto-discovered from the server - no manual configuration needed.

    Args:
        connector_data: MCP server configuration (command, args, env)
        search_space_id: ID of the search space to attach the connector to
        session: Database session
        user: Current authenticated user

    Returns:
        Created MCP connector with server configuration

    Raises:
        HTTPException: If search space not found or permission denied
    """
    try:
        # Check user has permission to create connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this search space",
        )

        # Create the connector with single server config
        db_connector = SearchSourceConnector(
            name=connector_data.name,
            connector_type=SearchSourceConnectorType.MCP_CONNECTOR,
            is_indexable=False,  # MCP connectors are not indexable
            config={"server_config": connector_data.server_config.model_dump()},
            periodic_indexing_enabled=False,
            indexing_frequency_minutes=None,
            search_space_id=search_space_id,
            user_id=user.id,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        logger.info(
            f"Created MCP connector {db_connector.id} "
            f"for user {user.id} in search space {search_space_id}"
        )

        # Convert to read schema
        connector_read = SearchSourceConnectorRead.model_validate(db_connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create MCP connector: {e!s}"
        ) from e


@router.get("/connectors/mcp", response_model=list[MCPConnectorRead])
async def list_mcp_connectors(
    search_space_id: int = Query(..., description="Search space ID"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all MCP connectors for a search space.

    Args:
        search_space_id: ID of the search space
        session: Database session
        user: Current authenticated user

    Returns:
        List of MCP connectors with their tool configurations
    """
    try:
        # Check user has permission to read connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this search space",
        )

        # Fetch MCP connectors
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
                SearchSourceConnector.search_space_id == search_space_id,
            )
        )

        connectors = result.scalars().all()
        return [
            MCPConnectorRead.from_connector(SearchSourceConnectorRead.model_validate(c))
            for c in connectors
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list MCP connectors: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list MCP connectors: {e!s}"
        ) from e


@router.get("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def get_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific MCP connector by ID.

    Args:
        connector_id: ID of the connector
        session: Database session
        user: Current authenticated user

    Returns:
        MCP connector with tool configurations
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to read connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get MCP connector: {e!s}"
        ) from e


@router.put("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def update_mcp_connector(
    connector_id: int,
    connector_update: MCPConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update an MCP connector.

    Args:
        connector_id: ID of the connector to update
        connector_update: Updated connector data
        session: Database session
        user: Current authenticated user

    Returns:
        Updated MCP connector
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to update connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to update this connector",
        )

        # Update fields
        if connector_update.name is not None:
            connector.name = connector_update.name

        if connector_update.server_config is not None:
            connector.config = {
                "server_config": connector_update.server_config.model_dump()
            }

        connector.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(connector)

        logger.info(f"Updated MCP connector {connector_id}")

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update MCP connector: {e!s}"
        ) from e


@router.delete("/connectors/mcp/{connector_id}", status_code=204)
async def delete_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete an MCP connector.

    Args:
        connector_id: ID of the connector to delete
        session: Database session
        user: Current authenticated user
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to delete connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        await session.delete(connector)
        await session.commit()

        logger.info(f"Deleted MCP connector {connector_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete MCP connector: {e!s}"
        ) from e


@router.post("/connectors/mcp/test")
async def test_mcp_server_connection(
    server_config: dict = Body(...),
    user: User = Depends(current_active_user),
):
    """
    Test connection to an MCP server and fetch available tools.

    This endpoint allows users to test their MCP server configuration
    before saving it, similar to Cursor's flow.

    Supports two transport types:
    - stdio: Local process with command, args, env
    - streamable-http/http/sse: Remote HTTP server with url, headers

    Args:
        server_config: Server configuration
        user: Current authenticated user

    Returns:
        Connection status and list of available tools
    """
    try:
        from app.agents.new_chat.tools.mcp_client import (
            test_mcp_connection,
            test_mcp_http_connection,
        )

        transport = server_config.get("transport", "stdio")

        # HTTP transport (streamable-http, http, sse)
        if transport in ("streamable-http", "http", "sse"):
            url = server_config.get("url")
            headers = server_config.get("headers", {})

            if not url:
                raise HTTPException(
                    status_code=400, detail="Server URL is required for HTTP transport"
                )

            result = await test_mcp_http_connection(url, headers, transport)
            return result

        # stdio transport (default)
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not command:
            raise HTTPException(
                status_code=400, detail="Server command is required for stdio transport"
            )

        # Test the connection
        result = await test_mcp_connection(command, args, env)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test MCP connection: {e!s}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to test connection: {e!s}",
            "tools": [],
        }
