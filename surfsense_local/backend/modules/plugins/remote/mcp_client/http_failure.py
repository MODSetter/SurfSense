"""HTTP and network failures, turned into `ServerError` with a sentence and whether to retry."""

import httpx2

from modules.plugins.remote.mcp_client.server_error import ServerError

RETRYABLE_STATUSES = frozenset({408, 429})


def refused(
    status: int, reason: str | None = None, scopes: list[str] | None = None
) -> ServerError:
    retryable = status in RETRYABLE_STATUSES or status >= 500
    return ServerError(
        f"the plugin's server answered {status}",
        retryable=retryable,
        status=status,
        reason=reason,
        scopes=scopes,
    )


def unreachable(error: httpx2.TransportError) -> ServerError:
    return ServerError(
        f"the plugin's server could not be reached: {error}", retryable=True
    )
