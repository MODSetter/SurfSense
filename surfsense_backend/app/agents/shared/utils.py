"""
Utility functions for SurfSense agents.

This module provides shared utility functions used across the new_chat agent modules.
"""

from datetime import UTC, datetime, timedelta


def parse_date_or_datetime(value: str) -> datetime:
    """
    Parse either an ISO date (YYYY-MM-DD) or ISO datetime into an aware UTC datetime.

    - If `value` is a date, interpret it as start-of-day in UTC.
    - If `value` is a datetime without timezone, assume UTC.

    Args:
        value: ISO date or datetime string

    Returns:
        Aware datetime object in UTC

    Raises:
        ValueError: If the date string is empty or invalid
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Empty date string")

    # Date-only
    if "T" not in raw:
        d = datetime.fromisoformat(raw).date()
        return datetime(d.year, d.month, d.day, tzinfo=UTC)

    # Datetime (may be naive)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def resolve_date_range(
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """
    Resolve a date range, defaulting to the last 2 years if not provided.
    Ensures start_date <= end_date.

    Args:
        start_date: Optional start datetime (UTC)
        end_date: Optional end datetime (UTC)

    Returns:
        Tuple of (resolved_start_date, resolved_end_date) in UTC
    """
    resolved_end = end_date or datetime.now(UTC)
    resolved_start = start_date or (resolved_end - timedelta(days=730))

    if resolved_start > resolved_end:
        resolved_start, resolved_end = resolved_end, resolved_start

    return resolved_start, resolved_end
