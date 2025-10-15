"""
ConnectorSchedule routes for CRUD operations:
POST /connector-schedules/ - Create a new schedule
GET /connector-schedules/ - List all schedules for the current user
GET /connector-schedules/{schedule_id} - Get a specific schedule
PUT /connector-schedules/{schedule_id} - Update a specific schedule
DELETE /connector-schedules/{schedule_id} - Delete a specific schedule
PATCH /connector-schedules/{schedule_id}/toggle - Activate/deactivate a schedule
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    ConnectorSchedule,
    ScheduleType,
    SearchSourceConnector,
    SearchSpace,
    User,
    get_async_session,
)
from app.schemas import (
    ConnectorScheduleCreate,
    ConnectorScheduleRead,
    ConnectorScheduleUpdate,
)
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from app.utils.schedule_helpers import calculate_next_run

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/connector-schedules/", response_model=ConnectorScheduleRead)
async def create_connector_schedule(
    schedule: ConnectorScheduleCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new connector schedule.

    Each connector can have only one schedule per search space.
    The schedule will automatically calculate the next run time based on the schedule type.
    """
    try:
        # Verify connector belongs to user
        connector = await check_ownership(
            session, SearchSourceConnector, schedule.connector_id, user
        )

        # Verify connector is indexable
        if not connector.is_indexable:
            raise HTTPException(
                status_code=400,
                detail=f"Connector {connector.name} is not indexable and cannot be scheduled",
            )

        # Verify search space belongs to user
        await check_ownership(session, SearchSpace, schedule.search_space_id, user)

        # Ensure the connector belongs to the same search space
        if connector.search_space_id != schedule.search_space_id:
            raise HTTPException(
                status_code=400,
                detail="Connector does not belong to the provided search space",
            )

        # Check if schedule already exists for this connector-space pair
        result = await session.execute(
            select(ConnectorSchedule).filter(
                ConnectorSchedule.connector_id == schedule.connector_id,
                ConnectorSchedule.search_space_id == schedule.search_space_id,
            )
        )
        existing_schedule = result.scalars().first()
        if existing_schedule:
            raise HTTPException(
                status_code=409,
                detail=f"A schedule already exists for connector {schedule.connector_id} and search space {schedule.search_space_id}",
            )

        # Calculate next run time
        next_run_at = calculate_next_run(
            schedule.schedule_type, 
            schedule.cron_expression,
            schedule.daily_time,
            schedule.weekly_day,
            schedule.weekly_time,
            schedule.hourly_minute
        )

        # Create schedule (only DB columns)
        db_data = schedule.model_dump(
            include={
                "connector_id", 
                "search_space_id", 
                "schedule_type", 
                "cron_expression", 
                "daily_time",
                "weekly_day",
                "weekly_time",
                "hourly_minute",
                "is_active"
            }
        )
        db_schedule = ConnectorSchedule(**db_data, next_run_at=next_run_at)
        session.add(db_schedule)
        await session.commit()
        await session.refresh(db_schedule)

        logger.info(
            f"Created schedule {db_schedule.id} for connector {schedule.connector_id} (next run: {next_run_at})"
        )
        return db_schedule

    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A schedule already exists for this connector and search space: {e!s}",
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create connector schedule: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create connector schedule: {e!s}"
        ) from e


@router.get("/connector-schedules/", response_model=list[ConnectorScheduleRead])
async def read_connector_schedules(
    skip: int = 0,
    limit: int = 100,
    connector_id: int | None = None,
    search_space_id: int | None = None,
    is_active: bool | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all connector schedules for the current user.

    Optional filters:
    - connector_id: Filter by specific connector
    - search_space_id: Filter by specific search space
    - is_active: Filter by active/inactive status
    """
    try:
        # Build query to get schedules for connectors owned by user
        query = (
            select(ConnectorSchedule)
            .join(SearchSourceConnector)
            .filter(SearchSourceConnector.user_id == user.id)
        )

        # Apply filters
        if connector_id is not None:
            query = query.filter(ConnectorSchedule.connector_id == connector_id)
        if search_space_id is not None:
            query = query.filter(ConnectorSchedule.search_space_id == search_space_id)
        if is_active is not None:
            query = query.filter(ConnectorSchedule.is_active == is_active)

        result = await session.execute(query.offset(skip).limit(limit))
        return result.scalars().all()

    except Exception as e:
        logger.error(f"Failed to fetch connector schedules: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch connector schedules: {e!s}"
        ) from e


@router.get("/connector-schedules/{schedule_id}", response_model=ConnectorScheduleRead)
async def read_connector_schedule(
    schedule_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a specific connector schedule by ID."""
    try:
        # Get schedule
        result = await session.execute(
            select(ConnectorSchedule).filter(ConnectorSchedule.id == schedule_id)
        )
        schedule = result.scalars().first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Verify schedule's connector belongs to user
        await check_ownership(session, SearchSourceConnector, schedule.connector_id, user)

        return schedule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch connector schedule: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch connector schedule: {e!s}"
        ) from e


@router.put("/connector-schedules/{schedule_id}", response_model=ConnectorScheduleRead)
async def update_connector_schedule(
    schedule_id: int,
    schedule_update: ConnectorScheduleUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a connector schedule.

    Can update schedule_type, cron_expression, and is_active.
    If schedule_type changes, next_run_at is recalculated automatically.
    """
    try:
        # Get the existing schedule
        result = await session.execute(
            select(ConnectorSchedule).filter(ConnectorSchedule.id == schedule_id)
        )
        schedule = result.scalars().first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Verify schedule's connector belongs to user
        await check_ownership(session, SearchSourceConnector, schedule.connector_id, user)

        # Update fields that were provided
        update_data = schedule_update.model_dump(exclude_unset=True)
        
        # Check if any time-related fields changed (requiring next_run recalc)
        time_fields_changed = any(
            field in update_data 
            for field in ["daily_time", "weekly_day", "weekly_time", "hourly_minute"]
        )
        
        # If schedule_type is being updated, recalculate next_run_at
        if "schedule_type" in update_data or time_fields_changed:
            # Use the new schedule_type and existing values for calculation
            new_schedule_type = update_data.get("schedule_type", schedule.schedule_type)
            cron_expr = update_data.get("cron_expression", schedule.cron_expression)
            daily_time = update_data.get("daily_time", schedule.daily_time)
            weekly_day = update_data.get("weekly_day", schedule.weekly_day)
            weekly_time = update_data.get("weekly_time", schedule.weekly_time)
            hourly_minute = update_data.get("hourly_minute", schedule.hourly_minute)
            update_data["next_run_at"] = calculate_next_run(
                new_schedule_type, cron_expr, daily_time, weekly_day, weekly_time, hourly_minute
            )
        elif "cron_expression" in update_data and schedule.schedule_type == ScheduleType.CUSTOM:
            # If only cron_expression is updated for CUSTOM schedule, recalculate next_run_at
            update_data["next_run_at"] = calculate_next_run(
                schedule.schedule_type, 
                update_data["cron_expression"],
                schedule.daily_time,
                schedule.weekly_day,
                schedule.weekly_time,
                schedule.hourly_minute
            )

        # Apply updates
        for field, value in update_data.items():
            setattr(schedule, field, value)

        await session.commit()
        await session.refresh(schedule)

        logger.info(f"Updated schedule {schedule_id} with fields: {list(update_data.keys())}")
        return schedule

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update connector schedule: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update connector schedule: {e!s}"
        ) from e


@router.delete("/connector-schedules/{schedule_id}")
async def delete_connector_schedule(
    schedule_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete a connector schedule."""
    try:
        # Get the existing schedule
        result = await session.execute(
            select(ConnectorSchedule).filter(ConnectorSchedule.id == schedule_id)
        )
        schedule = result.scalars().first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Verify schedule's connector belongs to user
        await check_ownership(session, SearchSourceConnector, schedule.connector_id, user)

        # Delete the schedule
        await session.delete(schedule)
        await session.commit()

        logger.info(f"Deleted schedule {schedule_id}")
        return {"message": "Schedule deleted successfully"}

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete connector schedule: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete connector schedule: {e!s}"
        ) from e


@router.patch("/connector-schedules/{schedule_id}/toggle", response_model=ConnectorScheduleRead)
async def toggle_connector_schedule(
    schedule_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Toggle the active status of a connector schedule."""
    try:
        # Get the existing schedule
        result = await session.execute(
            select(ConnectorSchedule).filter(ConnectorSchedule.id == schedule_id)
        )
        schedule = result.scalars().first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Verify schedule's connector belongs to user
        await check_ownership(session, SearchSourceConnector, schedule.connector_id, user)

        # Toggle the active status
        schedule.is_active = not schedule.is_active
        await session.commit()
        await session.refresh(schedule)

        logger.info(f"Toggled schedule {schedule_id} to {'active' if schedule.is_active else 'inactive'}")
        return schedule

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to toggle connector schedule: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to toggle connector schedule: {e!s}"
        ) from e
 
