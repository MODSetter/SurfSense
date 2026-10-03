"""The protocol version both sides speak: agreed in `initialize`, named on each request after."""

from typing import Any

from fastapi import HTTPException, Request, status

# The one opencode 1.18.34's MCP client asks for (its SDK 1.29.0); recheck on a bump.
PROTOCOL_VERSIONS = ("2025-11-25",)


def initialized(params: dict[str, Any]) -> dict[str, Any]:
    """The answer to `initialize`: the version both sides speak, and that tools are offered."""
    asked = params.get("protocolVersion")
    return {
        "protocolVersion": asked
        if asked in PROTOCOL_VERSIONS
        else PROTOCOL_VERSIONS[0],
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "SurfSense", "version": "1"},
    }


def refuse_unknown_protocol(request: Request) -> None:
    """Refuse a version this server does not speak; a request that names none is let through."""
    version = request.headers.get("mcp-protocol-version")
    if version is not None and version not in PROTOCOL_VERSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"MCP protocol {version} is not supported"
        )
