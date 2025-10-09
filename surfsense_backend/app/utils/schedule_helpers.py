"""Helper utilities for calculating schedule next run times."""

from datetime import datetime, timedelta

from croniter import croniter

from app.db import ScheduleType


def calculate_next_run(
    schedule_type: ScheduleType, cron_expression: str | None = None
) -> datetime:
    """
    Calculate the next run time based on schedule type.

    Args:
        schedule_type: The type of schedule (HOURLY, DAILY, WEEKLY, CUSTOM)
        cron_expression: Optional cron expression for CUSTOM type

    Returns:
        datetime: The next scheduled run time

    Raises:
        ValueError: If schedule_type is CUSTOM but no cron_expression provided
    """
    now = datetime.now()

    if schedule_type == ScheduleType.HOURLY:
        # Run at the top of the next hour
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    elif schedule_type == ScheduleType.DAILY:
        # Run at 2 AM next day (off-peak hours)
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    elif schedule_type == ScheduleType.WEEKLY:
        # Run on Sunday at 2 AM
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and next_run <= now:
            days_until_sunday = 7
        next_run += timedelta(days=days_until_sunday)
        return next_run

    elif schedule_type == ScheduleType.CUSTOM:
        if not cron_expression:
            raise ValueError("cron_expression is required for CUSTOM schedule type")
        try:
            cron = croniter(cron_expression, now)
            return cron.get_next(datetime)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {cron_expression}") from e

    else:
        raise ValueError(f"Unknown schedule type: {schedule_type}")


def is_valid_cron_expression(expression: str) -> bool:
    """
    Validate a cron expression.

    Args:
        expression: The cron expression to validate

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        croniter(expression)
        return True
    except Exception:
        return False

