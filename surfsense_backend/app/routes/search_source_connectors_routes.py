"""
SearchSourceConnector routes for CRUD operations:
POST /search-source-connectors/ - Create a new connector
GET /search-source-connectors/ - List all connectors for the current user (optionally filtered by search space)
GET /search-source-connectors/{connector_id} - Get a specific connector
PUT /search-source-connectors/{connector_id} - Update a specific connector
DELETE /search-source-connectors/{connector_id} - Delete a specific connector
POST /search-source-connectors/{connector_id}/index - Index content from a connector to a search space

Note: OAuth connectors (Gmail, Drive, Slack, etc.) support multiple accounts per search space.
Non-OAuth connectors (BookStack, GitHub, etc.) are limited to one per search space.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

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
    SearchSourceConnectorBase,
    SearchSourceConnectorCreate,
    SearchSourceConnectorRead,
    SearchSourceConnectorUpdate,
)
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
    Delete a search source connector.
    Requires CONNECTORS_DELETE permission.
    """
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

        # Delete any periodic schedule associated with this connector
        if db_connector.periodic_indexing_enabled:
            success = delete_periodic_schedule(connector_id)
            if not success:
                logger.warning(
                    f"Failed to delete periodic schedule for connector {connector_id}"
                )

        await session.delete(db_connector)
        await session.commit()
        return {"message": "Search source connector deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete search source connector: {e!s}",
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
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Determine the actual date range to use
        if start_date is None:
            # Use last_indexed_at or default to 365 days ago
            if connector.last_indexed_at:
                today = datetime.now().date()
                if connector.last_indexed_at.date() == today:
                    # If last indexed today, go back 1 day to ensure we don't miss anything
                    indexing_from = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    indexing_from = connector.last_indexed_at.strftime("%Y-%m-%d")
            else:
                indexing_from = (datetime.now() - timedelta(days=365)).strftime(
                    "%Y-%m-%d"
                )
        else:
            indexing_from = start_date

        # For calendar connectors, default to today but allow future dates if explicitly provided
        if connector.connector_type in [
            SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
            SearchSourceConnectorType.LUMA_CONNECTOR,
        ]:
            # Default to today if no end_date provided (users can manually select future dates)
            indexing_to = today_str if end_date is None else end_date
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

            logger.info(
                f"Triggering web pages indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_crawled_urls_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Web page indexing started in the background."

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Indexing not supported for connector type: {connector.connector_type}",
            )

        return {
            "message": response_message,
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
            connector.last_indexed_at = datetime.now()
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
    try:
        # Index Slack messages without updating last_indexed_at (we'll do it separately)
        documents_processed, error_or_warning = await index_slack_messages(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Only update last_indexed_at if indexing was successful (either new docs or updated docs)
        if documents_processed > 0:
            await _update_connector_timestamp_by_id(session, connector_id)
            logger.info(
                f"Slack indexing completed successfully: {documents_processed} documents processed"
            )
        else:
            logger.error(
                f"Slack indexing failed or no documents processed: {error_or_warning}"
            )
    except Exception as e:
        logger.error(f"Error in background Slack indexing task: {e!s}")


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
        await run_notion_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
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
    try:
        # Index Notion pages without updating last_indexed_at (we'll do it separately)
        documents_processed, error_or_warning = await index_notion_pages(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Only update last_indexed_at if indexing was successful (either new docs or updated docs)
        if documents_processed > 0:
            await _update_connector_timestamp_by_id(session, connector_id)
            logger.info(
                f"Notion indexing completed successfully: {documents_processed} documents processed"
            )
        else:
            logger.error(
                f"Notion indexing failed or no documents processed: {error_or_warning}"
            )
    except Exception as e:
        logger.error(f"Error in background Notion indexing task: {e!s}")


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
    """Runs the GitHub indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_github_repos(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"GitHub indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"GitHub indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Critical error in run_github_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    """Runs the Linear indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_linear_issues(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Linear indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Linear indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Critical error in run_linear_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    try:
        # Index Discord messages without updating last_indexed_at (we'll do it separately)
        documents_processed, error_or_warning = await index_discord_messages(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Only update last_indexed_at if indexing was successful (either new docs or updated docs)
        if documents_processed > 0:
            await _update_connector_timestamp_by_id(session, connector_id)
            logger.info(
                f"Discord indexing completed successfully: {documents_processed} documents processed"
            )
        else:
            logger.error(
                f"Discord indexing failed or no documents processed: {error_or_warning}"
            )
    except Exception as e:
        logger.error(f"Error in background Discord indexing task: {e!s}")


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
    try:
        from app.tasks.connector_indexers.teams_indexer import index_teams_messages

        # Index Teams messages without updating last_indexed_at (we'll do it separately)
        documents_processed, error_or_warning = await index_teams_messages(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Update last_indexed_at after successful indexing (even if 0 new docs - they were checked)
        await _update_connector_timestamp_by_id(session, connector_id)
        logger.info(
            f"Teams indexing completed successfully: {documents_processed} documents processed. {error_or_warning or ''}"
        )
    except Exception as e:
        logger.error(f"Error in background Teams indexing task: {e!s}")


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
    """Runs the Jira indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_jira_issues(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Jira indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Jira indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_jira_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    """Runs the Confluence indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_confluence_pages(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Confluence indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Confluence indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_confluence_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    """Runs the ClickUp indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_clickup_tasks(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"ClickUp indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"ClickUp indexing successful for connector {connector_id}. Indexed {indexed_count} tasks."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_clickup_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    """Runs the Airtable indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_airtable_records(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Airtable indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Airtable indexing successful for connector {connector_id}. Indexed {indexed_count} records."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_airtable_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    """Runs the Google Calendar indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_google_calendar_events(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Google Calendar indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Google Calendar indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_google_calendar_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


async def run_google_gmail_indexing_with_new_session(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    max_messages: int,
    days_back: int,
):
    """Wrapper to run Google Gmail indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Google Gmail connector {connector_id} into space {search_space_id} for {max_messages} messages from the last {days_back} days"
    )
    async with async_session_maker() as session:
        await run_google_gmail_indexing(
            session, connector_id, search_space_id, user_id, max_messages, days_back
        )
    logger.info(
        f"Background task finished: Indexing Google Gmail connector {connector_id}"
    )


async def run_google_gmail_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    max_messages: int,
    days_back: int,
):
    """Runs the Google Gmail indexing task and updates the timestamp."""
    try:
        # Convert days_back to start_date string in YYYY-MM-DD format
        from datetime import datetime, timedelta

        start_date_obj = datetime.now() - timedelta(days=days_back)
        start_date = start_date_obj.strftime("%Y-%m-%d")
        end_date = None  # No end date, index up to current time

        indexed_count, error_message = await index_google_gmail_messages(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,
            max_messages=max_messages,
        )
        if error_message:
            logger.error(
                f"Google Gmail indexing failed for connector {connector_id}: {error_message}"
            )
            # Optionally update status in DB to indicate failure
        else:
            logger.info(
                f"Google Gmail indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_google_gmail_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


async def run_google_drive_indexing(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    items_dict: dict,  # Dictionary with 'folders' and 'files' lists
):
    """Runs the Google Drive indexing task for folders and files and updates the timestamp."""
    try:
        from app.tasks.connector_indexers.google_drive_indexer import (
            index_google_drive_files,
            index_google_drive_single_file,
        )

        # Parse the structured data
        items = GoogleDriveIndexRequest(**items_dict)
        total_indexed = 0
        errors = []

        # Index each folder
        for folder in items.folders:
            try:
                indexed_count, error_message = await index_google_drive_files(
                    session,
                    connector_id,
                    search_space_id,
                    user_id,
                    folder_id=folder.id,
                    folder_name=folder.name,
                    use_delta_sync=True,
                    update_last_indexed=False,
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

        if errors:
            logger.error(
                f"Google Drive indexing completed with errors for connector {connector_id}: {'; '.join(errors)}"
            )
        else:
            logger.info(
                f"Google Drive indexing successful for connector {connector_id}. Indexed {total_indexed} documents from {len(items.folders)} folder(s) and {len(items.files)} file(s)."
            )
            # Update the last indexed timestamp only on full success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_google_drive_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        # Optionally update status in DB to indicate failure


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
    try:
        # Index Luma events without updating last_indexed_at (we'll do it separately)
        documents_processed, error_or_warning = await index_luma_events(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Only update last_indexed_at if indexing was successful (either new docs or updated docs)
        if documents_processed > 0:
            await _update_connector_timestamp_by_id(session, connector_id)
            logger.info(
                f"Luma indexing completed successfully: {documents_processed} documents processed"
            )
        else:
            logger.error(
                f"Luma indexing failed or no documents processed: {error_or_warning}"
            )
    except Exception as e:
        logger.error(f"Error in background Luma indexing task: {e!s}")


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
    """Runs the Elasticsearch indexing task and updates the timestamp."""
    try:
        indexed_count, error_message = await index_elasticsearch_documents(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"Elasticsearch indexing failed for connector {connector_id}: {error_message}"
            )
        else:
            logger.info(
                f"Elasticsearch indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Critical error in run_elasticsearch_indexing for connector {connector_id}: {e}",
            exc_info=True,
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
    try:
        documents_processed, error_or_warning = await index_crawled_urls(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=False,  # Don't update timestamp in the indexing function
        )

        # Only update last_indexed_at if indexing was successful (either new docs or updated docs)
        if documents_processed > 0:
            await _update_connector_timestamp_by_id(session, connector_id)
            logger.info(
                f"Web page indexing completed successfully: {documents_processed} documents processed"
            )
        else:
            logger.error(
                f"Web page indexing failed or no documents processed: {error_or_warning}"
            )
    except Exception as e:
        logger.error(f"Error in background Web page indexing task: {e!s}")


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

    try:
        indexed_count, error_message = await index_bookstack_pages(
            session,
            connector_id,
            search_space_id,
            user_id,
            start_date,
            end_date,
            update_last_indexed=False,
        )
        if error_message:
            logger.error(
                f"BookStack indexing failed for connector {connector_id}: {error_message}"
            )
        else:
            logger.info(
                f"BookStack indexing successful for connector {connector_id}. Indexed {indexed_count} documents."
            )
            # Update the last indexed timestamp only on success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update
    except Exception as e:
        logger.error(
            f"Critical error in run_bookstack_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
