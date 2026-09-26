from datetime import UTC, datetime
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.llm.models import ProviderConnection

HOST_PREFIX = "host:"
# One row per host, by construction: the key *is* the hostname, so a destination
# cannot be added twice under two names. Searching, downloading weights and
# downloading an image model all reach this one, and the panel asks about the
# host rather than about each errand sent to it.
HUGGINGFACE = f"{HOST_PREFIX}huggingface.co"
# Contacted whether or not a connection points at them, so they are listed with
# no connection to discover them from.
BUILT_IN = (HUGGINGFACE,)


class EgressDeniedError(Exception):
    def __init__(self, destination: str, host: str | None = None) -> None:
        self.destination = destination
        self.host = host or host_of(destination)
        super().__init__(f"sending data to {self.host} is off in Settings > Network")


def host_of(destination: str) -> str:
    return destination.removeprefix(HOST_PREFIX)


def is_destination(value: str) -> bool:
    return value.startswith(HOST_PREFIX) and len(value) > len(HOST_PREFIX)


def host_destination(base_url: str) -> str | None:
    """None for a loopback host: nothing leaves the machine."""
    host = urlsplit(base_url).hostname or ""
    if host == "localhost" or _is_loopback(host):
        return None
    return f"{HOST_PREFIX}{host}"


def _is_loopback(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def require(
    session: Session, destination: str | None, host: str | None = None
) -> None:
    if destination is None:
        return
    row = session.get(EgressDestination, destination)
    if row is None or not row.enabled:
        raise EgressDeniedError(destination, host)
    row.last_call_at = datetime.now(UTC)


def set_enabled(session: Session, destination: str, enabled: bool) -> EgressDestination:
    row = session.get(EgressDestination, destination)
    if row is None:
        row = EgressDestination(destination=destination)
        session.add(row)
    row.enabled = enabled
    session.flush()
    return row


def list_destinations(session: Session) -> list[EgressDestination]:
    """Includes destinations never allowed, so the panel can show them off."""
    hosts = {
        destination
        for base_url in session.scalars(select(ProviderConnection.base_url))
        if (destination := host_destination(base_url)) is not None
    }
    rows = {row.destination: row for row in session.scalars(select(EgressDestination))}
    return [
        rows.get(destination)
        or EgressDestination(destination=destination, enabled=False)
        for destination in [*BUILT_IN, *sorted(hosts - set(BUILT_IN))]
    ]
