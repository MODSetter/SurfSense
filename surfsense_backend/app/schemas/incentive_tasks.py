"""
Schemas for incentive tasks API.
"""

from datetime import datetime

from pydantic import BaseModel

from app.db import INCENTIVE_TASKS_CONFIG, IncentiveTaskType


class IncentiveTaskInfo(BaseModel):
    """Information about an available incentive task."""

    task_type: IncentiveTaskType
    title: str
    description: str
    # Credit reward in USD micro-units (1_000_000 == $1.00).
    credit_micros_reward: int
    action_url: str
    completed: bool
    completed_at: datetime | None = None


class IncentiveTasksResponse(BaseModel):
    """Response containing all available incentive tasks with completion status."""

    tasks: list[IncentiveTaskInfo]
    total_credit_micros_earned: int


class CompleteTaskRequest(BaseModel):
    """Request to mark a task as completed."""

    task_type: IncentiveTaskType


class CompleteTaskResponse(BaseModel):
    """Response after completing a task."""

    success: bool
    message: str
    credit_micros_awarded: int
    new_balance_micros: int


class TaskAlreadyCompletedResponse(BaseModel):
    """Response when task was already completed."""

    success: bool
    message: str
    completed_at: datetime


def get_task_info(task_type: IncentiveTaskType) -> dict | None:
    """Get task configuration by type."""
    return INCENTIVE_TASKS_CONFIG.get(task_type)


def get_all_task_types() -> list[IncentiveTaskType]:
    """Get all configured task types."""
    return list(INCENTIVE_TASKS_CONFIG.keys())
