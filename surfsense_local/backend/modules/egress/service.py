from datetime import UTC, datetime
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.llm.models import ProviderConnection

IMAGE_MODEL_PULL = "image_model_pull"
# Two destinations on one host, because they are two different consents.
# `model_download` is a repo the user named and asked for. `model_search` is
# text they are typing, sent as they type it. Collapsing them into one would
# make allowing a download also allow everything typed into a search box.
MODEL_DOWNLOAD = "model_download"
MODEL_SEARCH = "model_search"
HOST_PREFIX = "host:"
# Named, not host:-prefixed, so downloading weights is listed and revocable in
# Settings > Network like any other call, and reads as a download rather than as
# a connection that would carry prompts and documents.
HOSTS = {
    IMAGE_MODEL_PULL: "huggingface.co",
    MODEL_DOWNLOAD: "huggingface.co",
    MODEL_SEARCH: "huggingface.co",
}


class EgressDeniedError(Exception):
    def __init__(self, destination: str, host: str | None = None) -> None:
        self.destination = destination
        self.host = host or host_of(destination)
        super().__init__(f"sending data to {self.host} is off in Settings > Network")


def host_of(destination: str) -> str:
    return HOSTS.get(destination) or destination.removeprefix(HOST_PREFIX)


def is_destination(value: str) -> bool:
    return value in HOSTS or (
        value.startswith(HOST_PREFIX) and len(value) > len(HOST_PREFIX)
    )


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
        for destination in [
            IMAGE_MODEL_PULL,
            MODEL_DOWNLOAD,
            MODEL_SEARCH,
            *sorted(hosts),
        ]
    ]
