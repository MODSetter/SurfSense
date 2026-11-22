"""When the plugin host last gave a verdict, kept for the API's life: a restart asks again."""

from datetime import UTC, datetime, timedelta

# As often as a plugin's tools are listed before a turn.
STALE_AFTER = timedelta(minutes=5)


class VerdictClock:
    def __init__(self) -> None:
        self.answered_at: datetime | None = None

    def due(self, now: datetime, expiry: datetime | None) -> bool:
        """Stale after five minutes, or once the license file's expiry has passed since.

        The file's date only says when to ask: the host may know of a renewal it does not.
        """
        if self.answered_at is None or now - self.answered_at >= STALE_AFTER:
            return True
        return expiry is not None and self.answered_at < expiry <= now

    def answered(self, now: datetime) -> None:
        self.answered_at = now


CLOCK = VerdictClock()


def now() -> datetime:
    return datetime.now(UTC)
