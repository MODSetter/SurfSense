"""Helper utilities for calculating schedule next run times."""

from datetime import datetime, timedelta, time, timezone

from croniter import croniter

from app.db import ScheduleType


def calculate_next_run(
    schedule_type: ScheduleType, 
    cron_expression: str | None = None,
    daily_time: time | None = None,
    weekly_day: int | None = None,
    weekly_time: time | None = None,
    hourly_minute: int | None = None,
) -> datetime:
    """
    Calculate the next run time based on schedule type with enhanced time options.

    Args:
        schedule_type: The type of schedule (HOURLY, DAILY, WEEKLY, CUSTOM)
        cron_expression: Optional cron expression for CUSTOM type
        daily_time: Optional time for DAILY schedules (default: 02:00)
        weekly_day: Optional day for WEEKLY schedules (0=Monday, 6=Sunday, default: 6)
        weekly_time: Optional time for WEEKLY schedules (default: 02:00)
        hourly_minute: Optional minute for HOURLY schedules (0-59, default: 0)

    Returns:
        datetime: The next scheduled run time (timezone-aware in UTC)

    Raises:
        ValueError: If schedule_type is CUSTOM but no cron_expression provided
    """
    now = datetime.now(timezone.utc)

    if schedule_type == ScheduleType.HOURLY:
        # Run at the specified minute of the next hour
        minute = hourly_minute if hourly_minute is not None else 0
        next_run = (now + timedelta(hours=1)).replace(minute=minute, second=0, microsecond=0)
        return next_run.replace(tzinfo=timezone.utc)

    elif schedule_type == ScheduleType.DAILY:
        # Run at the specified time next day
        target_time = daily_time if daily_time is not None else time(2, 0)  # Default 2 AM
        next_run = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run.replace(tzinfo=timezone.utc)

    elif schedule_type == ScheduleType.WEEKLY:
        # Run on the specified day at the specified time
        target_day = weekly_day if weekly_day is not None else 6  # Default Sunday
        target_time = weekly_time if weekly_time is not None else time(2, 0)  # Default 2 AM
        
        next_run = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
        
        # Calculate days until target day
        days_until_target = (target_day - now.weekday()) % 7
        if days_until_target == 0 and next_run <= now:
            days_until_target = 7
        
        next_run += timedelta(days=days_until_target)
        return next_run.replace(tzinfo=timezone.utc)

    elif schedule_type == ScheduleType.CUSTOM:
        if not cron_expression:
            raise ValueError("cron_expression is required for CUSTOM schedule type")
        try:
            cron = croniter(cron_expression, now)
            next_run = cron.get_next(datetime)
            # Ensure the returned datetime is timezone-aware in UTC
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            return next_run
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

