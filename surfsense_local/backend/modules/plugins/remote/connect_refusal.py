"""Why connecting to a remote server failed: one outcome per failure, in SurfSense's words.

Every connect path, adding, a registry connect, a new key or headers, reads failures here,
so each one is named the same way everywhere. A server's own text never reaches a refusal.
"""

from fastapi import HTTPException, status

from modules.plugins.remote.mcp_client.server_error import ServerError

SIGN_IN_STATUSES = frozenset({401, 403})


def connect_refusal(error: ServerError) -> HTTPException:
    if error.status in SIGN_IN_STATUSES:
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_needs_sign_in",
                "message": "This server needs a key or a sign-in before it lists its tools.",
            },
        )
    if _not_mcp(error):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "plugin_not_mcp",
                "message": "This address doesn't answer as an MCP server.",
            },
        )
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        {
            "code": "plugin_unreachable",
            "message": "The plugin's server could not be reached.",
        },
    )


def _not_mcp(error: ServerError) -> bool:
    """Something answered, but not as MCP: another 4xx, or an answer the client could not read.

    A network failure, a timeout or a 5xx is the server being down, which may pass.
    """
    if error.status is not None:
        return 400 <= error.status < 500
    return not error.retryable
