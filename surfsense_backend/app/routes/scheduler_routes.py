"""
Scheduler management routes for monitoring and controlling the connector scheduler service.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_async_session
from app.schemas import ConnectorScheduleRead
from app.services.connector_scheduler_service import get_scheduler
from app.users import User, current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    user: User = Depends(current_active_user),
):
    """
    Get the current status of the connector scheduler service.
    
    Returns information about:
    - Whether the scheduler is running
    - Number of active jobs
    - Configuration details
    - Active job details
    """
    try:
        scheduler = await get_scheduler()
        status = await scheduler.get_scheduler_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get scheduler status: {e}"
        ) from e


@router.post("/scheduler/schedules/{schedule_id}/force-execute")
async def force_execute_schedule(
    schedule_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_active_user),
):
    """
    Force execution of a specific schedule (for testing/manual triggers).
    
    This bypasses the normal schedule timing and immediately executes
    the connector sync for the specified schedule.
    """
    try:
        scheduler = await get_scheduler()
        
        # Add the force execution to background tasks
        background_tasks.add_task(
            _force_execute_schedule_task,
            scheduler,
            schedule_id
        )
        
        return {
            "message": f"Force execution of schedule {schedule_id} has been queued",
            "schedule_id": schedule_id
        }
        
    except Exception as e:
        logger.error(f"Error force executing schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to force execute schedule: {e}"
        ) from e


async def _force_execute_schedule_task(scheduler, schedule_id: int):
    """Background task to force execute a schedule."""
    try:
        success = await scheduler.force_execute_schedule(schedule_id)
        if success:
            logger.info(f"Successfully force executed schedule {schedule_id}")
        else:
            logger.error(f"Failed to force execute schedule {schedule_id}")
    except Exception as e:
        logger.error(f"Error in force execute task for schedule {schedule_id}: {e}")


@router.get("/scheduler/schedules/upcoming", response_model=list[Dict[str, Any]])
async def get_upcoming_schedules(
    limit: int = 10,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a list of upcoming scheduled connector syncs.
    
    Useful for monitoring and debugging scheduled operations.
    """
    try:
        from app.db import ConnectorSchedule, SearchSourceConnector, SearchSpace
        
        # Get upcoming schedules for connectors owned by the user
        query = (
            select(ConnectorSchedule)
            .options(
                selectinload(ConnectorSchedule.connector),
                selectinload(ConnectorSchedule.search_space),
            )
            .join(SearchSourceConnector)
            .filter(
                SearchSourceConnector.user_id == user.id,
                ConnectorSchedule.is_active == True,  # noqa: E712
                ConnectorSchedule.next_run_at.isnot(None),
            )
            .order_by(ConnectorSchedule.next_run_at)
            .limit(limit)
        )
        
        result = await session.execute(query)
        schedules = result.scalars().all()
        
        upcoming_schedules = []
        for schedule in schedules:
            upcoming_schedules.append({
                "schedule_id": schedule.id,
                "connector_name": schedule.connector.name,
                "connector_type": schedule.connector.connector_type.value,
                "search_space_name": schedule.search_space.name,
                "schedule_type": schedule.schedule_type.value,
                "next_run_at": schedule.next_run_at,
                "last_run_at": schedule.last_run_at,
                "cron_expression": schedule.cron_expression,
            })
            
        return upcoming_schedules
        
    except Exception as e:
        logger.error(f"Error getting upcoming schedules: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get upcoming schedules: {e}"
        ) from e


@router.get("/scheduler/schedules/recent-executions", response_model=list[Dict[str, Any]])
async def get_recent_schedule_executions(
    limit: int = 20,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a list of recently executed connector schedules.
    
    Shows the execution history for monitoring and debugging.
    """
    try:
        from app.db import ConnectorSchedule, SearchSourceConnector, Log
        
        # Get recent executions from the logs table
        query = (
            select(Log)
            .join(SearchSourceConnector, Log.metadata["connector_id"].astext.cast(Integer) == SearchSourceConnector.id)
            .filter(
                SearchSourceConnector.user_id == user.id,
                Log.task_name.like("scheduled_sync_%"),
            )
            .order_by(Log.created_at.desc())
            .limit(limit)
        )
        
        result = await session.execute(query)
        logs = result.scalars().all()
        
        executions = []
        for log in logs:
            executions.append({
                "log_id": log.id,
                "task_name": log.task_name,
                "status": log.status,
                "created_at": log.created_at,
                "completed_at": log.completed_at,
                "connector_id": log.metadata.get("connector_id") if log.metadata else None,
                "schedule_id": log.metadata.get("schedule_id") if log.metadata else None,
                "error_message": log.error_message,
                "documents_processed": log.metadata.get("documents_processed") if log.metadata else None,
            })
            
        return executions
        
    except Exception as e:
        logger.error(f"Error getting recent schedule executions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent schedule executions: {e}"
        ) from e
