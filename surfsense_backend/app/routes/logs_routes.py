from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Log, LogLevel, LogStatus, SearchSpace, User, get_async_session
from app.schemas import LogCreate, LogRead, LogUpdate
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()


@router.post("/logs", response_model=LogRead)
async def create_log(
    log: LogCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create a new log entry."""
    try:
        # Check if the user owns the search space
        await check_ownership(session, SearchSpace, log.search_space_id, user)

        db_log = Log(**log.model_dump())
        session.add(db_log)
        await session.commit()
        await session.refresh(db_log)
        return db_log
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create log: {e!s}"
        ) from e


@router.get("/logs", response_model=list[LogRead])
async def read_logs(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    level: LogLevel | None = None,
    status: LogStatus | None = None,
    source: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get logs with optional filtering."""
    try:
        # Build base query - only logs from user's search spaces
        query = (
            select(Log)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
            .order_by(desc(Log.created_at))  # Most recent first
        )

        # Apply filters
        filters = []

        if search_space_id is not None:
            await check_ownership(session, SearchSpace, search_space_id, user)
            filters.append(Log.search_space_id == search_space_id)

        if level is not None:
            filters.append(Log.level == level)

        if status is not None:
            filters.append(Log.status == status)

        if source is not None:
            filters.append(Log.source.ilike(f"%{source}%"))

        if start_date is not None:
            filters.append(Log.created_at >= start_date)

        if end_date is not None:
            filters.append(Log.created_at <= end_date)

        if filters:
            query = query.filter(and_(*filters))

        # Apply pagination
        result = await session.execute(query.offset(skip).limit(limit))
        return result.scalars().all()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch logs: {e!s}"
        ) from e


@router.get("/logs/{log_id}", response_model=LogRead)
async def read_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a specific log by ID."""
    try:
        # Get log and verify user owns the search space
        result = await session.execute(
            select(Log)
            .join(SearchSpace)
            .filter(Log.id == log_id, SearchSpace.user_id == user.id)
        )
        log = result.scalars().first()

        if not log:
            raise HTTPException(status_code=404, detail="Log not found")

        return log
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch log: {e!s}"
        ) from e


@router.put("/logs/{log_id}", response_model=LogRead)
async def update_log(
    log_id: int,
    log_update: LogUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Update a log entry."""
    try:
        # Get log and verify user owns the search space
        result = await session.execute(
            select(Log)
            .join(SearchSpace)
            .filter(Log.id == log_id, SearchSpace.user_id == user.id)
        )
        db_log = result.scalars().first()

        if not db_log:
            raise HTTPException(status_code=404, detail="Log not found")

        # Update only provided fields
        update_data = log_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_log, field, value)

        await session.commit()
        await session.refresh(db_log)
        return db_log
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update log: {e!s}"
        ) from e


@router.delete("/logs/{log_id}")
async def delete_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete a log entry."""
    try:
        # Get log and verify user owns the search space
        result = await session.execute(
            select(Log)
            .join(SearchSpace)
            .filter(Log.id == log_id, SearchSpace.user_id == user.id)
        )
        db_log = result.scalars().first()

        if not db_log:
            raise HTTPException(status_code=404, detail="Log not found")

        await session.delete(db_log)
        await session.commit()
        return {"message": "Log deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete log: {e!s}"
        ) from e


@router.get("/logs/search-space/{search_space_id}/summary")
async def get_logs_summary(
    search_space_id: int,
    hours: int = 24,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Get a summary of logs for a search space in the last X hours."""
    try:
        # Check ownership
        await check_ownership(session, SearchSpace, search_space_id, user)

        # Calculate time window
        since = datetime.utcnow().replace(microsecond=0) - timedelta(hours=hours)

        # Get logs from the time window
        result = await session.execute(
            select(Log)
            .filter(
                and_(Log.search_space_id == search_space_id, Log.created_at >= since)
            )
            .order_by(desc(Log.created_at))
        )
        logs = result.scalars().all()

        # Create summary
        summary = {
            "total_logs": len(logs),
            "time_window_hours": hours,
            "by_status": {},
            "by_level": {},
            "by_source": {},
            "active_tasks": [],
            "recent_failures": [],
        }

        # Count by status and level
        for log in logs:
            # Status counts
            status_str = log.status.value
            summary["by_status"][status_str] = (
                summary["by_status"].get(status_str, 0) + 1
            )

            # Level counts
            level_str = log.level.value
            summary["by_level"][level_str] = summary["by_level"].get(level_str, 0) + 1

            # Source counts
            if log.source:
                summary["by_source"][log.source] = (
                    summary["by_source"].get(log.source, 0) + 1
                )

            # Active tasks (IN_PROGRESS)
            if log.status == LogStatus.IN_PROGRESS:
                task_name = (
                    log.log_metadata.get("task_name", "Unknown")
                    if log.log_metadata
                    else "Unknown"
                )
                summary["active_tasks"].append(
                    {
                        "id": log.id,
                        "task_name": task_name,
                        "message": log.message,
                        "started_at": log.created_at,
                        "source": log.source,
                    }
                )

            # Recent failures
            if log.status == LogStatus.FAILED and len(summary["recent_failures"]) < 10:
                task_name = (
                    log.log_metadata.get("task_name", "Unknown")
                    if log.log_metadata
                    else "Unknown"
                )
                summary["recent_failures"].append(
                    {
                        "id": log.id,
                        "task_name": task_name,
                        "message": log.message,
                        "failed_at": log.created_at,
                        "source": log.source,
                        "error_details": log.log_metadata.get("error_details")
                        if log.log_metadata
                        else None,
                    }
                )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate logs summary: {e!s}"
        ) from e
