"""A plugin's host recorded as called when the gateway sends a runtime's request to it,
as every other egress is, for Settings > Network."""

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress.last_calls import LastCalls, record_last_call

_calls = LastCalls()


async def record_call(session: Session, url: str) -> None:
    destination = _calls.due(urlsplit(url).hostname or "")
    if destination is not None:
        await transact(session, record_last_call, destination)
