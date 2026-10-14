"""Why connecting to a remote server failed, as the screen's 4xx or 5xx with a sentence."""

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
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        {"code": "plugin_unreachable", "message": f"Could not connect: {error}."},
    )
