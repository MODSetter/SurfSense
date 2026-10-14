"""Retrying a request that is safe to send again: never `tools/call`, which may have acted."""

from collections.abc import Awaitable, Callable

import anyio

from modules.plugins.remote.mcp_client.server_error import ServerError

RETRIES = 2
# Short: a listing is waited on by a person or a turn, and a server down for longer stays down.
BACKOFF_SECONDS = 0.2


async def retried[T](send: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(RETRIES + 1):
        try:
            return await send()
        except ServerError as error:
            if not error.retryable or attempt == RETRIES:
                raise
            await anyio.sleep(BACKOFF_SECONDS * (attempt + 1))
    raise AssertionError("unreachable")
