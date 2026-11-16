"""The SDK's errors, turned into ours: a forgotten session, or a server failure.

The SDK reports every failing HTTP status as one internal error, so the status is
recorded from the response itself: a 503 is worth retrying, a 401 means sign in again.
"""

from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_REQUEST

from modules.plugins.remote.mcp_client.http_failure import refused
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.session_expired import SessionExpiredError

SESSION_TERMINATED = "Session terminated"


def translated(
    error: MCPError,
    failed_status: int | None,
    reason: str | None = None,
    scopes: list[str] | None = None,
) -> Exception:
    if error.code == INVALID_REQUEST and error.message == SESSION_TERMINATED:
        return SessionExpiredError()
    # The HTTP status decides, whatever code a JSON-RPC error body carries: a 401 with
    # one, as Zapier sends, is still a sign-in, and its words never reach the user.
    if failed_status is not None:
        return refused(failed_status, reason, scopes)
    return ServerError(error.message)
