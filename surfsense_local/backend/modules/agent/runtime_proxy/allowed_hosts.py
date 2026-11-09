"""Where a runtime may connect, each host on its port: nothing for opencode, whose plugins are
reached through the gateway on loopback, which the proxy never sees.

Kept in memory, so a connection takes no write lock: read again from the database once a
commit changes a destination's consent, and at least every TTL_SECONDS. A host allowed is
recorded as called, as every other egress is.
"""

import itertools
import time

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, sessionmaker

from modules.egress.last_calls import LastCalls, record_last_call
from modules.egress.models import EgressDestination

HTTPS_PORT = 443
TTL_SECONDS = 2.0

# Bumped after each commit that changed a destination's consent; a set built before is stale.
_generation = 0


class AllowedHosts:
    """One proxy's view of the hosts it lets through, and when it last recorded each one called."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._built: tuple[int, float, frozenset[tuple[str, int]]] | None = None
        self._calls = LastCalls()

    def current(self) -> frozenset[tuple[str, int]] | None:
        """The hosts, or None when they must be read again: no database, so callable on the event loop."""
        if self._built is None:
            return None
        generation, at, hosts = self._built
        if generation != _generation or time.monotonic() - at > TTL_SECONDS:
            return None
        return hosts

    def read(self) -> frozenset[tuple[str, int]]:
        """Read the hosts from the database; for the threadpool."""
        # Taken first, so a commit landing while this reads makes the result stale.
        generation = _generation
        with self._sessions() as session:
            hosts = self._ready(session)
        self._built = (generation, time.monotonic(), hosts)
        return hosts

    def _ready(self, session: Session) -> frozenset[tuple[str, int]]:
        """The hosts this proxy lets through, read from the database: none, for opencode."""
        return frozenset()

    def call_to_record(self, host: str) -> str | None:
        """The destination to record as called, when its last record is old enough."""
        return self._calls.due(host)

    def record_call(self, destination: str) -> None:
        """Note the destination's last call; for the threadpool."""
        with self._sessions() as session:
            record_last_call(session, destination)
            session.commit()


@event.listens_for(Session, "after_flush")
def _note_consent(session: Session, _context: object) -> None:
    """Mark a flush that changed a destination's consent; a last call alone changes none."""
    added_or_deleted = itertools.chain(session.new, session.deleted)
    if any(isinstance(row, EgressDestination) for row in added_or_deleted) or any(
        isinstance(row, EgressDestination) and _changed(row) for row in session.dirty
    ):
        session.info["consent_changed"] = True


def _changed(row: object) -> bool:
    return any(
        attribute.history.has_changes()
        for attribute in inspect(row).attrs
        if attribute.key != "last_call_at"
    )


@event.listens_for(Session, "after_commit")
def _consent_committed(session: Session) -> None:
    global _generation
    if session.info.pop("consent_changed", False):
        _generation += 1


@event.listens_for(Session, "after_rollback")
def _consent_rolled_back(session: Session) -> None:
    session.info.pop("consent_changed", None)
