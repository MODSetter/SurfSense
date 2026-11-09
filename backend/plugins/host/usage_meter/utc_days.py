"""Days as the meter keeps them: UTC dates written YYYY-MM-DD."""

import calendar
from datetime import UTC, date, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def day_of(moment: datetime) -> str:
    return moment.astimezone(UTC).date().isoformat()


def day_before(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def months_before(day: str, months: int) -> str:
    """The same day of the month `months` earlier, or that month's last day."""
    then = date.fromisoformat(day)
    year, month = divmod(then.year * 12 + then.month - 1 - months, 12)
    month += 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(then.day, last)).isoformat()


def is_day(text: str) -> bool:
    """Exactly YYYY-MM-DD, a real date."""
    try:
        return len(text) == 10 and date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False
