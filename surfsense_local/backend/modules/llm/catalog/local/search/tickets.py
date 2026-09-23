"""Install ids for builds no manifest names.

The renderer may not name a download, so the server mints an id for each build
it lists and keeps the build behind it. In memory and forgetful: a ticket
outliving its row would install something the user stopped looking at.
"""

import secrets
import time
from dataclasses import dataclass

from modules.llm.catalog.local.builds import Build

# The same window the renderer's search cache uses.
TTL_SECONDS = 300.0


@dataclass(frozen=True)
class Ticket:
    build: Build
    # The repo's own tag, which the exact check reads beside the header.
    pipeline_tag: str | None
    issued_at: float


class TicketStore:
    def __init__(self, *, ttl_seconds: float = TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._tickets: dict[str, Ticket] = {}

    def mint(
        self, build: Build, *, pipeline_tag: str | None = None, now: float | None = None
    ) -> str:
        self._expire(now)
        token = secrets.token_urlsafe(18)
        self._tickets[token] = Ticket(
            build, pipeline_tag, now if now is not None else time.monotonic()
        )
        return token

    def resolve(self, token: str, *, now: float | None = None) -> Ticket | None:
        self._expire(now)
        return self._tickets.get(token)

    def _expire(self, now: float | None) -> None:
        cutoff = (now if now is not None else time.monotonic()) - self._ttl
        for token, ticket in list(self._tickets.items()):
            if ticket.issued_at < cutoff:
                del self._tickets[token]
