"""A destination's last call, shown in Settings > Network, written at most once a minute per host
so a busy connection costs no write each time."""

import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.egress.service import host_destination

RECORD_SECONDS = 60.0


class LastCalls:
    def __init__(self) -> None:
        self._recorded: dict[str, float] = {}

    def due(self, host: str) -> str | None:
        """The destination to record as called, when its last record is old enough."""
        destination = host_destination(f"https://{host}")
        now = time.monotonic()
        if destination is None or now - self._recorded.get(host, -RECORD_SECONDS) < (
            RECORD_SECONDS
        ):
            return None
        self._recorded[host] = now
        return destination


def record_last_call(session: Session, destination: str) -> None:
    row = session.get(EgressDestination, destination)
    if row is not None:
        row.last_call_at = datetime.now(UTC)
