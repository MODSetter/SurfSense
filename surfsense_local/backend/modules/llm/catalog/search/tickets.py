"""Install ids for models that no manifest names.

`POST /llm/install` keys on a `catalog_id`, and the renderer is forbidden from
sending a repo, file, URL or path. A curated row's id comes from the manifest; a
search hit has no manifest entry, so there is nothing to key on.

Closing that by letting the renderer post a repo and file would hand the
frontend the ability to name an arbitrary download, which is exactly the
capability the install contract exists to withhold. So the server mints an id
when it prices a search result, and hands back only that.
"""

import secrets
import time
from dataclasses import dataclass

# The same window the search cache uses. A ticket outliving its row would let a
# stale screen install something the user is no longer looking at.
TTL_SECONDS = 300.0


@dataclass(frozen=True)
class InstallTicket:
    """One downloadable build, resolved server side."""

    repo: str
    file: str
    quantization: str
    size_bytes: int
    issued_at: float


class TicketStore:
    """In memory and deliberately forgetful."""

    def __init__(self, *, ttl_seconds: float = TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._tickets: dict[str, InstallTicket] = {}

    def mint(
        self, repo: str, file: str, quantization: str, size_bytes: int, *, now: float | None = None
    ) -> str:
        self._expire(now)
        token = secrets.token_urlsafe(18)
        self._tickets[token] = InstallTicket(
            repo, file, quantization, size_bytes, now if now is not None else time.monotonic()
        )
        return token

    def resolve(self, token: str, *, now: float | None = None) -> InstallTicket | None:
        """None for an expired or unknown id, which the route turns into the
        existing "stale or unknown, refresh the catalog" 422 rather than a second
        error class for the same failure."""
        self._expire(now)
        return self._tickets.get(token)

    def _expire(self, now: float | None) -> None:
        cutoff = (now if now is not None else time.monotonic()) - self._ttl
        for token, ticket in list(self._tickets.items()):
            if ticket.issued_at < cutoff:
                del self._tickets[token]
