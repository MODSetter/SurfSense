"""What a plugin requires of a request before its server sees it, such as a license.

A plugin's `server.py` names one as `access`; a plugin without one is open to every request.
"""

from dataclasses import dataclass
from typing import Protocol

from starlette.datastructures import Headers


@dataclass(frozen=True)
class Refusal:
    """An HTTP status and the `reason` the app shows the user."""

    status: int
    reason: str


class Access(Protocol):
    async def refusal(self, headers: Headers) -> Refusal | None:
        """None lets the request through."""
        ...
