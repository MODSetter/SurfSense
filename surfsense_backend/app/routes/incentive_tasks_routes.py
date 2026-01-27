"""
Incentive Tasks API routes.
Allows users to complete tasks (like starring GitHub repo) to earn free pages.
Each task can only be completed once per user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    INCENTIVE_TASKS_CONFIG,
    IncentiveTaskType,
    User,
    UserIncentiveTask,
    get_async_session,
)
from app.schemas.incentive_tasks import (
    CompleteTaskResponse,
    IncentiveTaskInfo,
    IncentiveTasksResponse,
    TaskAlreadyCompletedResponse,
)
from app.users import current_active_user

router = APIRouter(prefix="/incentive-tasks", tags=["incentive-tasks"])


@router.get("", response_model=IncentiveTasksResponse)
async def get_incentive_tasks(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> IncentiveTasksResponse:
    """
    Get all available incentive tasks with the user's completion status.
    """
    # Get all completed tasks for this user
    result = await session.execute(
        select(UserIncentiveTask).where(UserIncentiveTask.user_id == user.id)
    )
    completed_tasks = {task.task_type: task for task in result.scalars().all()}

    # Build task list with completion status
    tasks = []
    total_pages_earned = 0

    for task_type, config in INCENTIVE_TASKS_CONFIG.items():
        completed_task = completed_tasks.get(task_type)
        is_completed = completed_task is not None

        if is_completed:
            total_pages_earned += completed_task.pages_awarded

        tasks.append(
            IncentiveTaskInfo(
                task_type=task_type,
                title=config["title"],
                description=config["description"],
                pages_reward=config["pages_reward"],
                action_url=config["action_url"],
                completed=is_completed,
                completed_at=completed_task.completed_at if completed_task else None,
            )
        )

    return IncentiveTasksResponse(
        tasks=tasks,
        total_pages_earned=total_pages_earned,
    )


@router.post(
    "/{task_type}/complete",
    response_model=CompleteTaskResponse | TaskAlreadyCompletedResponse,
)
async def complete_task(
    task_type: IncentiveTaskType,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> CompleteTaskResponse | TaskAlreadyCompletedResponse:
    """
    Mark an incentive task as completed and award pages to the user.

    Each task can only be completed once. If the task was already completed,
    returns the existing completion information without awarding additional pages.
    """
    # Validate task type exists in config
    task_config = INCENTIVE_TASKS_CONFIG.get(task_type)
    if not task_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown task type: {task_type}",
        )

    # Check if task was already completed
    existing_task = await session.execute(
        select(UserIncentiveTask).where(
            UserIncentiveTask.user_id == user.id,
            UserIncentiveTask.task_type == task_type,
        )
    )
    existing = existing_task.scalar_one_or_none()

    if existing:
        return TaskAlreadyCompletedResponse(
            success=False,
            message="Task already completed",
            completed_at=existing.completed_at,
        )

    # Create the task completion record
    pages_reward = task_config["pages_reward"]
    new_task = UserIncentiveTask(
        user_id=user.id,
        task_type=task_type,
        pages_awarded=pages_reward,
    )
    session.add(new_task)

    # Update user's pages_limit
    user.pages_limit += pages_reward

    await session.commit()
    await session.refresh(user)

    return CompleteTaskResponse(
        success=True,
        message=f"Task completed! You earned {pages_reward} pages.",
        pages_awarded=pages_reward,
        new_pages_limit=user.pages_limit,
    )
