from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Log, LogLevel, LogStatus, SearchSpace, SkipReason, User, get_async_session
from app.schemas import (
    BulkDismissResponse,
    BulkRetryResponse,
    LogCreate,
    LogRead,
    LogUpdate,
    SkippedLog,
)
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


@router.post("/logs/{log_id}/retry", response_model=LogRead)
async def retry_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Retry a failed log/task."""
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

        # Check retry count limit (max 3 retries)
        if db_log.retry_count >= 3:
            raise HTTPException(
                status_code=400,
                detail="Maximum retry limit reached (3). Cannot retry this task.",
            )

        # Increment retry count and reset status to IN_PROGRESS
        db_log.retry_count += 1
        db_log.status = LogStatus.IN_PROGRESS
        db_log.message = f"Retrying task (retry #{db_log.retry_count})..."

        await session.commit()
        await session.refresh(db_log)
        return db_log
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to retry log: {e!s}"
        ) from e


@router.patch("/logs/{log_id}/dismiss", response_model=LogRead)
async def dismiss_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Dismiss a failed log/task."""
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

        # Set status to DISMISSED
        db_log.status = LogStatus.DISMISSED

        await session.commit()
        await session.refresh(db_log)
        return db_log
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to dismiss log: {e!s}"
        ) from e


@router.post("/logs/bulk-retry", response_model=BulkRetryResponse)
async def bulk_retry_logs(
    log_ids: list[int],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> BulkRetryResponse:
    """Retry multiple failed logs/tasks.

    Returns:
        BulkRetryResponse: Response containing:
            - retried: List of successfully retried log IDs
            - skipped: List of skipped logs with specific reasons for debugging
            - total: Total count of retried + skipped logs

    Skip Reasons:
        - LOG_NOT_FOUND: Log ID does not exist in the database
        - NOT_OWNER: User does not have permission to modify this log
        - RETRY_LIMIT_REACHED: Log has already been retried 3 times (maximum)

    Note:
        Skipped logs are categorized by specific reasons to enable better
        client-side debugging and error handling.
    """
    try:
        # Validate input
        if not log_ids:
            raise HTTPException(status_code=400, detail="No log IDs provided")

        # Use bulk UPDATE with conditions to retry eligible logs atomically
        # Only update logs where retry_count < 3 and user owns the search space
        stmt = (
            update(Log)
            .where(
                and_(
                    Log.id.in_(log_ids),
                    Log.retry_count < 3,
                    Log.search_space_id.in_(
                        select(SearchSpace.id).where(SearchSpace.user_id == user.id)
                    )
                )
            )
            .values(
                retry_count=Log.retry_count + 1,
                status=LogStatus.IN_PROGRESS,
                message=func.concat("Retrying task (retry #", Log.retry_count + 1, ")...")
            )
            .returning(Log.id)
        )
        result = await session.execute(stmt)
        retried_ids = [row[0] for row in result.all()]

        # Determine which logs were skipped (those in log_ids but not in retried_ids)
        # Categorize skipped logs by specific reasons for better debugging
        skipped_ids = set(log_ids) - set(retried_ids)
        skipped = []

        if skipped_ids:
            # Find logs that exist but user doesn't own (NOT_OWNER)
            not_owned_result = await session.execute(
                select(Log.id)
                .filter(
                    and_(
                        Log.id.in_(skipped_ids),
                        ~Log.search_space_id.in_(
                            select(SearchSpace.id).where(SearchSpace.user_id == user.id)
                        )
                    )
                )
            )
            not_owned_ids = {row[0] for row in not_owned_result.all()}

            # Find logs that exist, user owns, but retry limit reached (RETRY_LIMIT_REACHED)
            retry_limit_result = await session.execute(
                select(Log.id)
                .filter(
                    and_(
                        Log.id.in_(skipped_ids),
                        Log.retry_count >= 3,
                        Log.search_space_id.in_(
                            select(SearchSpace.id).where(SearchSpace.user_id == user.id)
                        )
                    )
                )
            )
            retry_limit_ids = {row[0] for row in retry_limit_result.all()}

            # Remaining logs are not found (LOG_NOT_FOUND)
            not_found_ids = skipped_ids - not_owned_ids - retry_limit_ids

            # Build skipped list with specific reasons
            for log_id in not_found_ids:
                skipped.append(SkippedLog(id=log_id, reason=SkipReason.LOG_NOT_FOUND))
            for log_id in not_owned_ids:
                skipped.append(SkippedLog(id=log_id, reason=SkipReason.NOT_OWNER))
            for log_id in retry_limit_ids:
                skipped.append(SkippedLog(id=log_id, reason=SkipReason.RETRY_LIMIT_REACHED))

        await session.commit()

        return BulkRetryResponse(
            retried=retried_ids,
            skipped=skipped,
            total=len(retried_ids) + len(skipped),
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to retry logs: {e!s}"
        ) from e


@router.post("/logs/bulk-dismiss", response_model=BulkDismissResponse)
async def bulk_dismiss_logs(
    log_ids: list[int],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> BulkDismissResponse:
    """Dismiss multiple failed logs/tasks.

    Returns:
        BulkDismissResponse: Response containing:
            - dismissed: List of successfully dismissed log IDs
            - skipped: List of skipped logs with specific reasons for debugging
            - total: Total count of dismissed + skipped logs

    Skip Reasons:
        - LOG_NOT_FOUND: Log ID does not exist in the database
        - NOT_OWNER: User does not have permission to modify this log

    Note:
        Breaking change: The 'total' field now includes both dismissed and skipped logs,
        whereas previously it only counted dismissed logs. This aligns with the
        bulk_retry_logs endpoint for API consistency.

        Skipped logs are categorized by specific reasons to enable better
        client-side debugging and error handling.
    """
    try:
        # Validate input
        if not log_ids:
            raise HTTPException(status_code=400, detail="No log IDs provided")

        # Use a single UPDATE with subquery to verify ownership and update atomically
        # This combines verification and update into one database operation
        stmt = (
            update(Log)
            .where(
                and_(
                    Log.id.in_(log_ids),
                    Log.search_space_id.in_(
                        select(SearchSpace.id).where(SearchSpace.user_id == user.id)
                    )
                )
            )
            .values(status=LogStatus.DISMISSED)
            .returning(Log.id)
        )
        result = await session.execute(stmt)
        dismissed_ids = [row[0] for row in result.all()]

        # Determine which logs were skipped (those in log_ids but not in dismissed_ids)
        # Categorize skipped logs by specific reasons for better debugging
        skipped_ids = set(log_ids) - set(dismissed_ids)
        skipped = []

        if skipped_ids:
            # Find logs that exist but user doesn't own (NOT_OWNER)
            not_owned_result = await session.execute(
                select(Log.id)
                .filter(
                    and_(
                        Log.id.in_(skipped_ids),
                        ~Log.search_space_id.in_(
                            select(SearchSpace.id).where(SearchSpace.user_id == user.id)
                        )
                    )
                )
            )
            not_owned_ids = {row[0] for row in not_owned_result.all()}

            # Remaining logs are not found (LOG_NOT_FOUND)
            not_found_ids = skipped_ids - not_owned_ids

            # Build skipped list with specific reasons
            for log_id in not_found_ids:
                skipped.append(SkippedLog(id=log_id, reason=SkipReason.LOG_NOT_FOUND))
            for log_id in not_owned_ids:
                skipped.append(SkippedLog(id=log_id, reason=SkipReason.NOT_OWNER))

        await session.commit()

        return BulkDismissResponse(
            dismissed=dismissed_ids,
            skipped=skipped,
            total=len(dismissed_ids) + len(skipped),
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to dismiss logs: {e!s}"
        ) from e
