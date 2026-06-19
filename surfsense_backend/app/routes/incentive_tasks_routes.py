"""
Incentive Tasks API routes.
Allows users to complete tasks (like starring GitHub repo) to earn free credits.
Each task can only be completed once per user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    INCENTIVE_TASKS_CONFIG,
    IncentiveTaskType,
    UserIncentiveTask,
    get_async_session,
)
from app.schemas.incentive_tasks import (
    CompleteTaskResponse,
    IncentiveTaskInfo,
    IncentiveTasksResponse,
    TaskAlreadyCompletedResponse,
)
from app.users import require_session_context

router = APIRouter(prefix="/incentive-tasks", tags=["incentive-tasks"])


@router.get("", response_model=IncentiveTasksResponse)
async def get_incentive_tasks(
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> IncentiveTasksResponse:
    """
    Get all available incentive tasks with the user's completion status.
    """
    user = auth.user
    # Get all completed tasks for this user
    result = await session.execute(
        select(UserIncentiveTask).where(UserIncentiveTask.user_id == user.id)
    )
    completed_tasks = {task.task_type: task for task in result.scalars().all()}

    # Build task list with completion status
    tasks = []
    total_credit_micros_earned = 0

    for task_type, config in INCENTIVE_TASKS_CONFIG.items():
        completed_task = completed_tasks.get(task_type)
        is_completed = completed_task is not None

        if is_completed:
            total_credit_micros_earned += completed_task.credit_micros_awarded

        tasks.append(
            IncentiveTaskInfo(
                task_type=task_type,
                title=config["title"],
                description=config["description"],
                credit_micros_reward=config["credit_micros_reward"],
                action_url=config["action_url"],
                completed=is_completed,
                completed_at=completed_task.completed_at if completed_task else None,
            )
        )

    return IncentiveTasksResponse(
        tasks=tasks,
        total_credit_micros_earned=total_credit_micros_earned,
    )


@router.post(
    "/{task_type}/complete",
    response_model=CompleteTaskResponse | TaskAlreadyCompletedResponse,
)
async def complete_task(
    task_type: IncentiveTaskType,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
) -> CompleteTaskResponse | TaskAlreadyCompletedResponse:
    """
    Mark an incentive task as completed and award credit to the user.

    Each task can only be completed once. If the task was already completed,
    returns the existing completion information without awarding additional credit.
    """
    user = auth.user
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
    credit_micros_reward = task_config["credit_micros_reward"]
    new_task = UserIncentiveTask(
        user_id=user.id,
        task_type=task_type,
        credit_micros_awarded=credit_micros_reward,
    )
    session.add(new_task)

    # Add the reward directly to the user's spendable wallet balance.
    user.credit_micros_balance = user.credit_micros_balance + credit_micros_reward

    await session.commit()
    await session.refresh(user)

    return CompleteTaskResponse(
        success=True,
        message=f"Task completed! You earned ${credit_micros_reward / 1_000_000:.2f} of credit.",
        credit_micros_awarded=credit_micros_reward,
        new_balance_micros=user.credit_micros_balance,
    )
