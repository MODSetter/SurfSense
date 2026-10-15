"""Where opencode may connect: the hosts of plugins ready now, each on its port.

Kept in memory, so a connection takes no write lock: read again from the database
once a commit touches anything readiness reads, and at least every TTL_SECONDS,
since a registry's delisting is a file, not a row. A host allowed is recorded as
called, as every other egress is, at most once every RECORD_SECONDS.
"""

import itertools
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, sessionmaker

from modules.egress.models import EgressDestination
from modules.egress.service import host_destination
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin, PluginSettings, PluginTool
from modules.plugins.installed.plugin_hosts import plugin_hosts

HTTPS_PORT = 443
TTL_SECONDS = 2.0
RECORD_SECONDS = 60.0

# The rows `list_tools` decides readiness from.
_READINESS = (InstalledPlugin, PluginTool, PluginSettings, EgressDestination)
# Bumped after each commit that touched them; a set built before it is stale.
_generation = 0


class AllowedHosts:
    """One proxy's view of the ready hosts, and when it last recorded each one called."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._built: tuple[int, float, frozenset[tuple[str, int]]] | None = None
        self._recorded: dict[str, float] = {}

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
            hosts = _ready_hosts(session)
        self._built = (generation, time.monotonic(), hosts)
        return hosts

    def call_to_record(self, host: str) -> str | None:
        """The destination to record as called, when its last record is old enough."""
        destination = host_destination(f"https://{host}")
        now = time.monotonic()
        if destination is None or now - self._recorded.get(host, -RECORD_SECONDS) < (
            RECORD_SECONDS
        ):
            return None
        self._recorded[host] = now
        return destination

    def record_call(self, destination: str) -> None:
        """Note the destination's last call; for the threadpool."""
        with self._sessions() as session:
            row = session.get(EgressDestination, destination)
            if row is not None:
                row.last_call_at = datetime.now(UTC)
            session.commit()


def _ready_hosts(session: Session) -> frozenset[tuple[str, int]]:
    """Every host of every ready plugin, on its URL's port, or 443 for one its entry declares.

    A ready plugin's hosts are all allowed in Settings > Network, or it would not be ready.
    """
    allowed = set()
    for plugin_id in dict.fromkeys(tool.plugin_id for tool in list_tools(session)):
        plugin = session.get_one(InstalledPlugin, plugin_id)
        url = urlsplit(plugin.url)
        ports = {url.hostname: url.port or HTTPS_PORT}
        for host in plugin_hosts(plugin):
            allowed.add((host, ports.get(host, HTTPS_PORT)))
    return frozenset(allowed)


@event.listens_for(Session, "after_flush")
def _note_readiness(session: Session, _context: object) -> None:
    """Mark a flush that changed a row readiness reads; a last call alone changes none."""
    added_or_deleted = itertools.chain(session.new, session.deleted)
    if any(isinstance(row, _READINESS) for row in added_or_deleted) or any(
        isinstance(row, _READINESS) and _changed(row) for row in session.dirty
    ):
        session.info["readiness_changed"] = True


def _changed(row: object) -> bool:
    return any(
        attribute.history.has_changes()
        for attribute in inspect(row).attrs
        if attribute.key != "last_call_at"
    )


@event.listens_for(Session, "after_commit")
def _readiness_committed(session: Session) -> None:
    global _generation
    if session.info.pop("readiness_changed", False):
        _generation += 1


@event.listens_for(Session, "after_rollback")
def _readiness_rolled_back(session: Session) -> None:
    session.info.pop("readiness_changed", None)
