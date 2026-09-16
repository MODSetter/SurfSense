from datetime import UTC, datetime
from ipaddress import ip_address
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.llm.models import ProviderConnection

OLLAMA_PULL = "ollama_pull"
IMAGE_MODEL_PULL = "image_model_pull"
HOST_PREFIX = "host:"
# Named, not host:-prefixed, so downloading weights is listed and revocable in
# Settings > Network like any other call, and reads as a download rather than as
# a connection that would carry prompts and documents.
HOSTS = {OLLAMA_PULL: "registry.ollama.ai", IMAGE_MODEL_PULL: "huggingface.co"}


class EgressDeniedError(Exception):
    def __init__(self, destination: str) -> None:
        self.destination = destination
        self.host = host_of(destination)
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


def require(session: Session, destination: str | None) -> None:
    if destination is None:
        return
    row = session.get(EgressDestination, destination)
    if row is None or not row.enabled:
        raise EgressDeniedError(destination)
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
        for destination in [OLLAMA_PULL, IMAGE_MODEL_PULL, *sorted(hosts)]
    ]
