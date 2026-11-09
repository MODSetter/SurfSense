"""A thread from opencode 1.x, read while 2.x is still importing its session.

2.x imports 1.x's sessions into its own database on its first start, in place,
in under a second for a few (core/src/database/v1-migration.bun.ts); until it
has, a known session answers 404. Its progress route is experimental, so a 404
in the first seconds this API sees a server serving is asked again instead.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx

# Well past the import of a few hundred sessions.
IMPORT_SECONDS = 10.0
_POLL_SECONDS = 0.25

# When this API first saw each server serving, by its pid.
_seen: dict[int, float] = {}


def _now() -> float:
    return time.monotonic()


class _Server(Protocol):
    async def server_pid(self) -> int: ...


def note_serving(pid: int) -> None:
    """The server answers with SurfSense's configuration; the first time is its start."""
    _seen.setdefault(pid, _now())


async def found_after_import[T](server: _Server, look: Callable[[], Awaitable[T]]) -> T:
    """`look`, asked again while a 404 may be a session not yet imported."""
    try:
        return await look()
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 404:
            raise
        seen = _seen.get(await server.server_pid())
        if seen is None or _now() - seen > IMPORT_SECONDS:
            raise
    while True:
        await asyncio.sleep(_POLL_SECONDS)
        try:
            return await look()
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404 or _now() - seen > IMPORT_SECONDS:
                raise
