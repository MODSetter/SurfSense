"""The SDK's errors, turned into ours: a forgotten session, or a server failure.

The SDK reports every failing HTTP status as one internal error, so the status is
recorded from the response itself: a 503 is worth retrying, a 401 means sign in again.
"""

from mcp.shared.exceptions import MCPError
from mcp_types import INTERNAL_ERROR, INVALID_REQUEST

from modules.plugins.remote.mcp_client.http_failure import refused
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.session_expired import SessionExpiredError

SESSION_TERMINATED = "Session terminated"


def translated(
    error: MCPError, failed_status: int | None, reason: str | None = None
) -> Exception:
    if error.code == INVALID_REQUEST and error.message == SESSION_TERMINATED:
        return SessionExpiredError()
    if error.code == INTERNAL_ERROR and failed_status is not None:
        return refused(failed_status, reason)
    return ServerError(error.message)
