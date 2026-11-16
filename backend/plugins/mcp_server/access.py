"""What a plugin requires of a request before its server sees it, such as a license.

A plugin's `server.py` names one as `access`; a plugin without one is open to every request.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol

from starlette.datastructures import Headers

# The license id a check matched the request's key to, never the key itself: set
# in the request's own context, where the host's usage meter reads it.
checked_license: ContextVar[str | None] = ContextVar("checked_license", default=None)


@dataclass(frozen=True)
class Refusal:
    """An HTTP status and the `reason` the app shows the user."""

    status: int
    reason: str


class Access(Protocol):
    async def refusal(self, headers: Headers) -> Refusal | None:
        """None lets the request through.

        A check that knows the key's license id sets `checked_license`, allowed or not.
        """
        ...
