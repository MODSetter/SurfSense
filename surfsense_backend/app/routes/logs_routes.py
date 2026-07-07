from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Log,
    LogLevel,
    LogStatus,
    Permission,
    Workspace,
    WorkspaceMembership,
    get_async_session,
)
from app.schemas import LogCreate, LogRead, LogUpdate
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


@router.post("/logs", response_model=LogRead)
async def create_log(
    log: LogCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Create a new log entry.
    Note: This is typically called internally. Requires LOGS_READ permission (since logs are usually system-generated).
    """
    try:
        # Check if the user has access to the workspace
        await check_permission(
            session,
            auth,
            log.workspace_id,
            Permission.LOGS_READ.value,
            "You don't have permission to access logs in this workspace",
        )

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
    workspace_id: int | None = None,
    level: LogLevel | None = None,
    status: LogStatus | None = None,
    source: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Get logs with optional filtering.
    Requires LOGS_READ permission for the workspace(s).
    """
    try:
        # Apply filters
        filters = []

        if workspace_id is not None:
            # Check permission for specific workspace
            await check_permission(
                session,
                auth,
                workspace_id,
                Permission.LOGS_READ.value,
                "You don't have permission to read logs in this workspace",
            )
            # Build query for specific workspace
            query = (
                select(Log)
                .filter(Log.workspace_id == workspace_id)
                .order_by(desc(Log.created_at))
            )
        else:
            # Build base query - logs from workspaces user has membership in
            query = (
                select(Log)
                .join(Workspace)
                .join(WorkspaceMembership)
                .filter(WorkspaceMembership.user_id == user.id)
                .order_by(desc(Log.created_at))
            )

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
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific log by ID.
    Requires LOGS_READ permission for the workspace.
    """
    try:
        result = await session.execute(select(Log).filter(Log.id == log_id))
        log = result.scalars().first()

        if not log:
            raise HTTPException(status_code=404, detail="Log not found")

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            log.workspace_id,
            Permission.LOGS_READ.value,
            "You don't have permission to read logs in this workspace",
        )

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
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a log entry.
    Requires LOGS_READ permission (logs are typically updated by system).
    """
    try:
        result = await session.execute(select(Log).filter(Log.id == log_id))
        db_log = result.scalars().first()

        if not db_log:
            raise HTTPException(status_code=404, detail="Log not found")

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            db_log.workspace_id,
            Permission.LOGS_READ.value,
            "You don't have permission to access logs in this workspace",
        )

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
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a log entry.
    Requires LOGS_DELETE permission for the workspace.
    """
    try:
        result = await session.execute(select(Log).filter(Log.id == log_id))
        db_log = result.scalars().first()

        if not db_log:
            raise HTTPException(status_code=404, detail="Log not found")

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            db_log.workspace_id,
            Permission.LOGS_DELETE.value,
            "You don't have permission to delete logs in this workspace",
        )

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


@router.get("/logs/workspaces/{workspace_id}/summary")
async def get_logs_summary(
    workspace_id: int,
    hours: int = 24,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a summary of logs for a workspace in the last X hours.
    Requires LOGS_READ permission for the workspace.
    """
    try:
        # Check permission
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.LOGS_READ.value,
            "You don't have permission to read logs in this workspace",
        )

        # Calculate time window
        since = datetime.utcnow().replace(microsecond=0) - timedelta(hours=hours)

        # Get logs from the time window
        result = await session.execute(
            select(Log)
            .filter(and_(Log.workspace_id == workspace_id, Log.created_at >= since))
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
                document_id = (
                    log.log_metadata.get("document_id") if log.log_metadata else None
                )
                connector_id = (
                    log.log_metadata.get("connector_id") if log.log_metadata else None
                )
                summary["active_tasks"].append(
                    {
                        "id": log.id,
                        "task_name": task_name,
                        "message": log.message,
                        "started_at": log.created_at,
                        "source": log.source,
                        "document_id": document_id,
                        "connector_id": connector_id,
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
